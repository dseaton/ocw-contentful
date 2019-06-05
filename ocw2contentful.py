from collections import defaultdict
import fnmatch
import json
import urllib

import boto3
from BeautifulSoup import BeautifulSoup
import contentful_management

from contentful_mapping import Translate
import secure


client = contentful_management.Client(secure.MANAGEMENT_API_TOKEN)
sid = secure.SPACE_ID
eid = secure.ENVIRONMENT_ID


class Ocw2Contentful(object):
    def __init__(self):
        """
        :param bucket: s3 bucket containing OCW data organized by course.
        """
        self.s3 = boto3.client("s3")
        self.T = Translate()
        department_url = "https://ocw.mit.edu/courses/find-by-number/departments.json"
        jdata = json.loads(urllib.urlopen(department_url).read())
        self.departments_by_num = dict((r['depNo'], r) for r in jdata)
        self.departments_by_title = dict((r['title'], r) for r in jdata)

    def get_courseware_metadata(self, ocw_url):
        """
        OCW URLs act as a unique identifier on ocw.mit.edu and also existin the uri pattern on s3. For example:
        URL: https://ocw.mit.edu/courses/urban-studies-and-planning/11-s943-development-planning-and-implementation-the-dialectic-of-theory-and-practice-fall-2017/
        s3 URI: Amazon S3: {BUCKET}/11-s943-development-planning-and-implementation-the-dialectic-of-theory-and-practice-fall-2017/
        
        :param ocw_url: str, making up the unique pattern in an OCW URL
        :return:
        """
        try: 
            prefix = ocw_url.split('/')[5]
        except:
            print("Something went wrong splitting your url with /.\n{}".format(ocw_url.split('/')))

        contents = self.s3.list_objects_v2(Bucket=secure.BUCKET, Prefix=prefix, StartAfter=prefix)['Contents']
        course_keys = [r['Key'] for r in contents if "_master.json" in r['Key']] 
        master_key = fnmatch.filter(course_keys, "*_master.json")[0]
        record = self.s3.get_object(Bucket=secure.BUCKET, Key=master_key)
        return json.loads(record['Body'].read().decode())

    def _make_camel(self, string):
        return ''.join(x for x in string.title() if x.isalnum())

    def _generate_tracking_title(self, courseware, title):
        return u"{}.{} - {}".format(
            courseware.fields()['department_number'], 
            courseware.fields()['master_course_number'], 
            title
        )

    def _clean_html(self, html):
        soup = BeautifulSoup(html)
        for tag in soup():
            for attribute in ["class", "id", "name", "style"]:
                del tag[attribute]

        for link_tag in soup.findAll('a'):
            print(link_tag["href"])
            if "/courses/" in link_tag["href"]:
                link_tag["href"] = "https://ocw.mit.edu/" + link_tag["href"]

        return soup

    def _prepare_metadata(self, record, delete_fields=None, additional_metadata=None):
        metadata = dict((k,record[k]) for k in record.keys() if isinstance(record[k], unicode)==True)
        if delete_fields:
            for k in delete_fields:
                if k in metadata:
                    del metadata[k]
        
        if additional_metadata:
            metadata.update(additional_metadata)

        return metadata

    def create_courseware(self, record):
        """
        Create an autoCourseware entry inside Contentful space. Does not create if the
        entry already exists.

        :param record: OCW json data for a single course.
        :return: Contentful Entry for autocourseware content type.
        """ 
        department_entry = self.create_department(self.departments_by_num[record['department_number']])
        tracking_title = u"{}.{} - {}".format(record['department_number'], record['master_course_number'], record['title'])
        metadata = self._prepare_metadata(
            record, 
            delete_fields=['uid', 'course_owner'],
            additional_metadata={
                u'department': [department_entry],
                u'tracking_title': tracking_title,
            },
        )
        return self.T.create_entry('courseware', record['uid'], metadata)

    def create_department(self, record):
        """
        Most department metadata for OCW are simply department numbers or titles (e.g., "7" or "Biology").
        Use self.departments_by_num to look up a record based on number (self.departments_by_title looks up by title).

        Each look up returns a department record from the old JSON data for OCW (best we have currently).
            {u'depNo': u'7', u'id': u'biology', u'title': u'Biology'}

        :param record: dict, with fields shown above
        """
        metadata = self._prepare_metadata(
            record,
            delete_fields=None,
            additional_metadata=None,
        )
        return self.T.create_entry('department', record['id'], metadata)

    def create_instructor(self, record, courseware):
        """
        Create an Instructor entry inside Contentful space. Does not create if the
        entry already exists. Example:
            {
                "middle_initial": "",
                "first_name": "Saif",
                "last_name": "Rayyan",
                "suffix": "",
                "title": "Rayyan, Saif",
                "mit_id": "",
                "department": "Physics",
                "directory_title": "Dr. Saif Rayyan",
                "uid": "abc123"
            }

        :param irecord: JSON record with instructor metadata
        :return: Contentful Entry for instructor content type 
        """
        ### Pattern Break: faculty listed by school, rather than department (e.g., School of Engineering)
        if record['department'] in self.departments_by_title:
            department_entry = self.create_department(
                self.departments_by_title[record['department']])
        else:
            department_entry = None

        metadata = self._prepare_metadata(
            record,
            delete_fields=['uid', 'mit_id', 'department'],
            additional_metadata={'department': [department_entry]},
        )
        return self.T.new_create_entry('instructor', record['uid'], metadata)

    def create_tag(self, record):
        """
        Old OCW tagging hierarchy: Topic -> Subtopic -> Speciality
        New tagging is just a list of keywords.
        "tags": [
            {
                "name": "design theory"
            },
            ...
        ]
    
        :param record: JSON record with tag metadata 
        :return: Contentful Entry for the tag 
        """
        uid = self._make_camel(record['name'][0:64])  # contentful uids max 64 char
        metadata = self._prepare_metadata(
            record, 
            delete_fields=None,
            additional_metadata=None,
        )
        return self.T.create_entry('tag', uid, metadata)

    def create_course_page(self, record, courseware):
        """
        Example Course File.
        {
            "uid": "cbe32f43b1c1045bb68f4b3197ae3655",
            "title": "Syllabus",
            "url": "/courses/civil-and-environmental-engineering/1-050-solid-mechanics-fall-2004/syllabus",
            "text": "<h2 class=\"subhead\">Course Meeting Times</h2> <p>Lectures: 3 sessions / week, 1 hour / session</p> <p>Labs: 2 sessions / week, 1 hour / session</p> <h3 class=\"subsubhead\">Course Introduction by Prof. Louis Bucciarelli</h3><p>65153023courseintroduction80419621</p><h2 class=\"subhead\">Objectives</h2> <p>The aim is to introduce students to the fundamental concepts and principles applied by engineers - whether civil, mechanical, aeronautical, etc.&nbsp;- in the design of structures of all sorts of sizes and purpose. We build upon the mathematics and physics courses of the freshman year, extending Newtonian Mechanics to address and understand the elastic behavior of trusses and frames, beams and cylinders. We aim also to engage students in the formulation and resolution of open-ended, design-type exercises, thereby bridging the divide between scientific theory and engineering practice.</p> <h2 class=\"subhead\">Textbook</h2> <p>Bucciarelli, Louis. <a href=\"http://store.doverpublications.com/0486468550.html\"><em>Engineering Mechanics for Structures</em></a>, Fall 2002. (The full text is published in the <a href=\"/courses/civil-and-environmental-engineering/1-050-solid-mechanics-fall-2004/readings\">readings section</a>.)</p> <p>Also required: Mead Quad Composition notebook.</p> <h2 class=\"subhead\">Other Resources</h2> <p><a href=\"http://www.amazon.com/exec/obidos/ASIN/0070134367/ref=nosim/mitopencourse-20\"><img alt=\"Buy at Amazon\" src=\"/images/a_logo_17.gif\" border=\"0\" align=\"absmiddle\" /></a> Crandall, S., N. Dahl, and T. Lardner. <em>An Intro. to the Mechanics of Solids</em>. New York, NY: McGraw-Hill, 1978. ISBN: 0070134367.</p> <p><a href=\"http://www.amazon.com/exec/obidos/ASIN/0534417930/ref=nosim/mitopencourse-20\"><img alt=\"Buy at Amazon\" src=\"/images/a_logo_17.gif\" border=\"0\" align=\"absmiddle\" /></a> Gere, James. <em>Mechanics of Materials</em>. 6th ed. New York, NY: Thomson Engineering Publishing,&nbsp;2003. ISBN: 0534417930.</p> <h2 class=\"subhead\">Grading</h2> <h3 class=\"subsubhead\">Quizzes 30%</h3> <p>There will be two one-hour, closed-book quizzes given during the semester.</p> <h3 class=\"subsubhead\">Design Exercises 40%</h3> <p>There will be six, short (~two, three day, take-home), open-ended exercises assigned throughout the semester. You will document your work in a journal (the Mead Composition book).</p> <h3 class=\"subsubhead\">Final Exam 30%</h3> <p>There will be a final exam.</p> <h2 class=\"subhead\">Homework</h2> <p>Homework will be assigned weekly, evaluated and returned to you (within a week). It will serve as a basis for discussion with the Teaching Assistant and Professor Bucciarelli.</p> <h2 class=\"subhead\">Design Exercise Journal Instructions</h2> <p>The journal, the quad-ruled composition book, 10 1/4 X 7 7/8 in, is for recording your work as you progress. Think of its contents, not as a polished text for presentation, nor as a complete record of every thought and word that comes to mind, but as a sufficiently full account of your thinking which would enable you to go back after some time has elapsed to reconstruct your reasoning, conjectures, and analysis. Write in ink. If you change your mind or find an error, don't erase; drawn a line through what is no longer wanted.</p> <p>Put your name, email, and phone number somewhere prominent; if lost, you want it returned. Leave the first few pages blank; make up a table of contents here as you go along. number the pages as you go along.</p> <p>At the end of each exercise, summarize, on one or two pages, the results of your efforts - e.g, a dimensioned sketch; an explanation of what parameters are critical; a restating of specifications; a note of difficult constraints.</p> <p>Two grades will be assigned for each exercise: One for &quot;presentation&quot;, the other for &quot;analysis&quot;. These two are not entirely independent. If your presentation is too cryptic or unreadable, evaluation of your analysis may be impossible and you will receive no credit. If your analysis omits references to sources - other students, a Web url, a reference textbook - your presentation will be judged inadequate and unethical. The two grades count equally.</p> <p>Think of it this way:</p> <p>Process is as important as product; means as important as ends.</p> <h2 class=\"subhead\">Important Note About Academic Honesty</h2> <p>We encourage you to work with your peers on homework and the design exercises. We do not condone copying. What is the difference? A valued and honest collaboration occurs when, for example, you &quot;get stuck&quot; early on in attacking an exercise and go to your classmate with a relevant question. Your colleague then has the opportunity to learn from your question as well as help you. You then bring something to the collaboration.</p> <p>Often we will form teams of two or three students to tackle the design exercises. And you can learn too from last year's problem sets and quizzes if used as a check or corrective when you seem to have hit a dead end. In doing the design exercises, you may have occasion to use the Web as a resource. We encourage that too. <strong>In all cases you are to reference your sources and collaborators, whether other students, the Web, archived solutions, etc.</strong></p>",
            "short_url": "syllabus",
            "type": "CourseSection",
            "parent_uid": "a7f822e2259e077a9adce834b44d72d2",
            "description": "The syllabus contains course objectives and list of materials for the course, along with the grading criteria."
        }
    
        :param record: JSON record with course page data
        :return: Contentful Entry for the course file 
        """
        metadata = self._prepare_metadata(
            record,
            delete_fields=['uid'],
            additional_metadata={
                u"tracking_title": self._generate_tracking_title(courseware, record['title']),
                u"clean_text": self._clean_text(record['text']),
            },
        )
        # Pattern break - needed to rename field due to unknown issues with naming convention.
        # Likely candidate for future refactor; requires changing content model in contentful.
        metadata[u'course_page_type'] = metadata.pop('type')
        return self.T.create_entry('course_page', record['uid'], metadata)

    def create_course_file(self, record, courseware):
        """
        Example Course File.
        {
            "uid": "3c80a0fc2e318beb48a7faa712431604",
            "caption": null,
            "file_type": "image/jpeg",
            "file_location": "https://open-learning-course-data-rc.s3.amazonaws.com/1-012-introduction-to-civil-engineering-design-spring-2002/3c80a0fc2e318beb48a7faa712431604_1-012s02.jpg",
            "title": "1-012s02.jpg",
            "alt_text": null,
            "platform_requirements": null,
            "credit": null,
            "parent_uid": "9a516c5aff0897dd339ac16282860e10",
            "description": null
        }
    
        :param record: JSON record with course file metadata (sparse)
        :return: Contentful Entry for the course file 
        """
        metadata = self._prepare_metadata(
            record,
            delete_fields=['uid', 'caption', 'platform_requirements'],
            additional_metadata={
                u"tracking_title": self._generate_tracking_title(courseware, record['title']),
                u'courseware': courseware,
            },
        )
        return self.T.create_entry('course_file', record['uid'], metadata)

    def create_course_embedded_media(self, record, courseware):
        """
            "course_embedded_media": {
                "65153023courseintroduction80419621": {
                    "technical_location": "https://ocw.mit.edu/courses/civil-and-environmental-engineering/1-050-solid-mechanics-fall-2004/syllabus/course-introduction",
                    "inline_embed_id": "65153023courseintroduction80419621",
                    "uid": "0b773e28a6376e2f3e85d80c42f4d6ea",
                    "title": "Course Introduction",
                    "parent_uid": "cbe32f43b1c1045bb68f4b3197ae3655",
                    "embedded_media": [
                        {
                            "media_info": "qlLUs2hRa_A",
                            "title": "Video-YouTube-Stream",
                            "id": "Video-YouTube-Stream",
                            "parent_uid": "0b773e28a6376e2f3e85d80c42f4d6ea",
                            "uid": "c2a29047b0b525c63d3ef77c416c892a"
                        },
                        {
                            "media_info": "https://img.youtube.com/vi/qlLUs2hRa_A/default.jpg",
                            "title": "Thumbnail-YouTube-JPG",
                            "id": "Thumbnail-YouTube-JPG",
                            "parent_uid": "0b773e28a6376e2f3e85d80c42f4d6ea",
                            "uid": "59a071c2521544a251cfb03aae2da7cb"
                        },
                        {
                            "media_info": "https://archive.org/download/MIT1.050F04/mit-ocw-1.050-facultyint-bucciarelli-04apr2004-220k.mp4",
                            "title": "Video-Internet Archive-MP4",
                            "id": "Video-InternetArchive-MP4",
                            "parent_uid": "0b773e28a6376e2f3e85d80c42f4d6ea",
                            "uid": "9138c24b7689860cf6befc7d829af28c"
                        }
                    ],
                    "id": "course-introduction"
                }
            },
        """
        metadata = self._prepare_metadata(
            record,
            delete_fields=['embedded_media'],
            additional_metadata={
                u"tracking_title": self._generate_tracking_title(courseware, record['title']),
                u'courseware': [courseware],
            },
        )
        return self.T.create_entry('embedded_media', record['uid'], metadata)

    def add_courseware(self, ocw_url):
        """
        Main routine to add a single course from OCW to Contentful.
        """
        #Grab the single course record from OCW JSON data
        record = self.get_courseware_metadata(ocw_url)

        #Step 1: create the basic metadata for a courseware entry in Contentful
        courseware = self.create_courseware(record)

        # #Step 2: add department
        # department = self.create_department(
        #     self.departments_by_num[record['department_number']])
        # courseware.department = [department]
        # courseware.save()

        # #Step 3: iterate over the faculty list; create if does not exist, link to courseware
        # courseware.instructors = [self.create_instructor(
        #     f, courseware) for f in record['instructors']]
        # courseware.save()

        # #Step 4: iterate through course tags and attach to courseware
        # # Update new_courseware with tag clinks
        # courseware.tags = [self.create_tag(t) for t in record['tags']]
        # courseware.save()

        # #Step 5: iterate through course pages and attach to courseware
        # courseware.course_pages = [self.create_course_page(cp, courseware) for cp in record['course_pages']]
        # print([p.sys['id'] for p in courseware.course_pages])
        # courseware.save()

        #Step 6: iterate through course files, create them, then go back and add them to each course page
        page_links = defaultdict(list)
        for cf in record['course_files']:
            page_links[cf['parent_uid']].append(
                self.create_course_file(cf, courseware))

        # # Link all files
        # courseware.course_files = list(
        #     set(j for i in page_links for j in page_links[i]))  # Grabbing unique entries
        # courseware.save()

        # # Link to specific course pages
        # for key in page_links:
        #     try:
        #         # print(key, page_links[key])
        #         course_page = client.entries(sid, eid).find(key)
        #         course_page.files = page_links[key]
        #         course_page.save()
        #         print("Added {} files to {} page.".format(
        #             len(page_links[key]), key))
        #     except Exception as e:
        #         print("Issue saving entries to course pages: {}".format(key))
        #         print(e)

        # #Step 7: iterate through embedded media, create entries, and attach to course page
        # em_links = defaultdict(list)
        # for key in record['course_embedded_media']:
        #     page = record['course_embedded_media'][key]
        #     em = {r['id']: r['media_info'][0:200]
        #           for r in page['embedded_media'] if r["id"] == "Video-YouTube-Stream"}
        #     page.update(em)
        #     page['technical_location'] = page['technical_location'][0:250]
        #     em_links[page['parent_uid']].append(
        #         self.create_course_embedded_media(page, courseware))

        # for key in em_links:
        #     try:
        #         course_page = client.entries(sid, eid).find(key)
        #         course_page.files = em_links[key]
        #         course_page.save()
        #         print("Added {} files to {} page.".format(
        #             len(em_links[key]), key))
        #     except Exception as e:
        #         print("Issue saving media to course pages: {}".format(key))
        #         print(e)

        return courseware


if __name__ == "__main__":
    '''
    Examples of populating a Contentful space with OCW content.
    '''
    from pprint import pprint
    import urllib

    
    # url = 'https://ocw.mit.edu/courses/aeronautics-and-astronautics/16-01-unified-engineering-i-ii-iii-iv-fall-2005-spring-2006/'
    # url = 'https://ocw.mit.edu/courses/physics/8-01sc-classical-mechanics-fall-2016/'
    # url = 'https://ocw.mit.edu/courses/civil-and-environmental-engineering/1-050-solid-mechanics-fall-2004'
    # url = 'https://ocw.mit.edu/courses/mathematics/18-06-linear-algebra-spring-2010'
    # url = 'https://ocw.mit.edu/courses/mathematics/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/'
    # url = 'https://ocw.mit.edu/courses/biology/7-13-experimental-microbial-genetics-fall-2008/'
    # url = 'https://ocw.mit.edu/courses/physics/8-591j-systems-biology-fall-2014/'
    # url = 'https://ocw.mit.edu/courses/materials-science-and-engineering/3-024-electronic-optical-and-magnetic-properties-of-materials-spring-2013/'
    
    ### Rapid Feedback from Krishna
    url = 'https://ocw.mit.edu/courses/physics/8-06-quantum-physics-iii-spring-2005/'
    
    ### Educator and Scholar Course
    # url = 'https://ocw.mit.edu/courses/chemistry/5-111sc-principles-of-chemical-science-fall-2014'
    # url = 'https://ocw.mit.edu/courses/mechanical-engineering/2-087-engineering-math-differential-equations-and-linear-algebra-fall-2014'
    
    ### Eliz Request 6.033
    # url = 'https://ocw.mit.edu/courses/electrical-engineering-and-computer-science/6-033-computer-system-engineering-spring-2018/'
    
    # OCW = Ocw2Contentful()
    # c = OCW.add_courseware(url)
    # print("Success creating courseware: {}".format(c))

    OCW = Ocw2Contentful()
    text = """
        <p>Some Topics have a related experiment in the class <em>8.13-8.14: Experimental Physics I &amp; II &quot;Junior Lab,&quot;</em> which is usually taken concurrently with Quantum Physics III.</p>
            <div class="maintabletemplate">
            <table summary="See table caption for summary.">
                <caption class="invisible">Related resources table.</caption>
                <thead>
                    <tr>
                        <th scope="col">LEC&nbsp;#</th>
                        <th scope="col">TOPICS</th>
                        <th scope="col">RELATED&nbsp;EXPERIMENTS</th>
                    </tr>
                </thead>
                <tbody>
                    <tr class="row">
                        <td>1</td>
                        <td>Natural Units</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr class="alt-row">
                        <td>2-4</td>
                        <td>Degenerate Fermi Systems</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr class="row">
                        <td>4-8</td>
                        <td>Charged Particles in a Magnetic Field</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr class="alt-row">
                        <td>9-12</td>
                        <td>Time-independent Perturbation Theory</td>
                        <td>
                        <p><a href="/courses/physics/8-13-14-experimental-physics-i-ii-junior-lab-fall-2007-spring-2008/labs/lab11">Optical Emission Spectra of Hydrogenic Atoms</a></p>
                        <p><a href="/courses/physics/8-13-14-experimental-physics-i-ii-junior-lab-fall-2007-spring-2008/labs/lab15">21-cm Radio Astrophysics</a></p>
                        <p><a href="/courses/physics/8-13-14-experimental-physics-i-ii-junior-lab-fall-2007-spring-2008/labs/lab16">The Zeeman Effect</a></p>
                        <p><a href="/courses/physics/8-13-14-experimental-physics-i-ii-junior-lab-fall-2007-spring-2008/labs/lab17">Optical Pumping of Rubidium Vapor</a></p>
                        <p><a href="/courses/physics/8-13-14-experimental-physics-i-ii-junior-lab-fall-2007-spring-2008/labs/lab19">X-Ray Physics</a></p>
                        <p><a href="/courses/physics/8-13-14-experimental-physics-i-ii-junior-lab-fall-2007-spring-2008/labs/lab21">Doppler-Free Laser Spectroscopy</a></p>
                        </td>
                    </tr>
                    <tr class="row">
                        <td>13-15</td>
                        <td>Variational and Semi-classical Methods</td>
                        <td><a href="/courses/physics/8-13-14-experimental-physics-i-ii-junior-lab-fall-2007-spring-2008/labs/lab20">Superconductivity</a></td>
                    </tr>
                    <tr class="alt-row">
                        <td>16-18</td>
                        <td>The Adiabatic Approximation and Berry's Phase</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr class="row">
                        <td>19-23</td>
                        <td>Scattering</td>
                        <td>
                        <p><a href="/courses/physics/8-13-14-experimental-physics-i-ii-junior-lab-fall-2007-spring-2008/labs/lab6">The Franck-Hertz Experiment</a></p>
                        <p><a href="/courses/physics/8-13-14-experimental-physics-i-ii-junior-lab-fall-2007-spring-2008/labs/lab10">Rutherford Scattering</a></p>
                        </td>
                    </tr>
                    <tr class="alt-row">
                        <td>23-24</td>
                        <td>Time-dependent Perturbation Theory</td>
                        <td>
                        <p><a href="/courses/physics/8-13-14-experimental-physics-i-ii-junior-lab-fall-2007-spring-2008/labs/lab17">Optical Pumping of Rubidium Vapor</a>&nbsp;</p>
                        <p><a href="/courses/physics/8-13-14-experimental-physics-i-ii-junior-lab-fall-2007-spring-2008/labs/lab21">Doppler-Free Laser Spectroscopy</a></p>
                        </td>
                    </tr>
                    <tr class="row">
                        <td>25</td>
                        <td>Quantum Computing</td>
                        <td><a href="/courses/physics/8-13-14-experimental-physics-i-ii-junior-lab-fall-2007-spring-2008/labs/lab22">Quantum Information Processing with NMR</a></td>
                    </tr>
                </tbody>
            </table>
            </div>
    """
    from pprint import pprint
    OCW._clean_html(text)


    # OCW = Ocw2Contentful()
    # counter = 0
    # for k,v in OCW.departments_by_num.iteritems():
    #     if counter < 10: 
    #         dept_url = "https://ocw.mit.edu/courses/{}/{}.json".format(v['id'], v['id'])
    #         dept_data = json.loads(urllib.urlopen(dept_url).read())
    #         course_record = dept_data[4]
    #         course_url = course_record[course_record.keys()[0]]['course_path']
    #         print("Parsing: {}".format(course_url))
    #         c = OCW.add_courseware(course_url)
    #         print("Success creating courseware: {}".format(c))
    #         counter = counter + 1
    
