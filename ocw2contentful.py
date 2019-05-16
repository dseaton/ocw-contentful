from collections import defaultdict
import fnmatch
import json
import urllib

import boto3
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
        self.departments = dict((r['depNo'], r) for r in jdata)

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

    def _create_media_resource(self, media_record, courseware_uid):
        """
        OCW media resources. Formatted as a list of individual records. Single example from list of media resources:
            [
                {u'Lecture 23: Inflation': {
                    u'path': u'courses/physics/8-286-the-early-universe-fall-2013/video-lectures/lecture-23-inflation', 
                    u'YouTube': {u'youtube_id': u'PsfyE1-s9Rs'}
                }
                },
                ...
            ] 
        :param media_record: media resource entry from OCW JSON data. 
        :param courseware_uid: Contentful unique id that lets us associate a course with this tag.
        :return: mediaResource entry from Contentful.
        """
        contentful_uid = media_record[media_record.keys()[0]]['YouTube']['youtube_id']

        m_meta = {
            'title': media_record.keys()[0],
            'youtube_id': contentful_uid,
            'path': media_record[media_record.keys()[0]]['path'],
            'courseware': courseware_uid,
        }
        return self.T.create_entry('mediaResource', contentful_uid, m_meta)

    

    def _create_department(self, drecord):
        """
        Given a department number, for example:
            "department_number": "1"

        Use the old JSON data to look up metadata for the department and create an entry.
        :param dept_number: str, giving MIT code for department (can contain letters, CC is Concourse)
        """
        contentful_uid = drecord['id']
        metadata = dict((k,drecord[k]) for k in drecord.keys() if isinstance(drecord[k], unicode)==True)
        return self.T.create_entry('department', contentful_uid, metadata)
        

    def _create_courseware(self, record):
        """
        Create an autoCourseware entry inside Contentful space. Does not create if the
        entry already exists.

        :param record: OCW json data for a single course.
        :return: Contentful Entry for autocourseware content type.
        """ 
        courseware_meta = dict((k,record[k]) for k in record.keys() if isinstance(record[k], unicode)==True)
        added_meta = {
            u'tracking_title': u"{}.{} - {}".format(
                record['department_number'], 
                record['master_course_number'], 
                record['title']
            ),
        }
        courseware_meta.update(added_meta)
        for k in ['uid', 'course_owner']:
            del courseware_meta[k]
    
        return self.T.create_entry('courseware', record['uid'], courseware_meta)

    def _create_instructor(self, irecord):
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
        metadata = dict((k,irecord[k]) for k in irecord.keys() if isinstance(irecord[k], unicode)==True)
        for k in ['uid', 'mit_id', 'department']:
            del metadata[k]

        return self.T.create_entry('instructor', irecord['uid'], metadata)

    def _create_tag(self, trecord):
        """
        Old OCW tagging hierarchy: Topic -> Subtopic -> Speciality
        New tagging is just a list of keywords.
        "tags": [
            {
                "name": "design theory"
            },
            ...
        ]
    
        :param trecord: JSON record with tag metadata (sparse)
        :return: Contentful Entry for the tag 
        """
        contentful_uid = self._make_camel(trecord['name'][0:64]) # contentful uids only 64 char long
        metadata = dict((k,trecord[k]) for k in trecord.keys() if isinstance(trecord[k], unicode)==True)
        return self.T.create_entry('tag', contentful_uid, metadata)

    def _create_course_file(self, cfrecord, courseware):
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
    
        :param cfrecord: JSON record with course file metadata (sparse)
        :param parent_entry: contentful entry that will serve as a reference field (e.g., here we want to associate a course file with a course page) 
        :return: Contentful Entry for the course file 
        """
        metadata = dict((k,cfrecord[k]) for k in cfrecord.keys() if isinstance(cfrecord[k], unicode)==True)
        added_meta = {
            u'tracking_title': self._generate_tracking_title(courseware, cfrecord['title']),
            u'courseware': courseware,
        }
        metadata.update(added_meta)
        for k in ['uid', 'caption', 'platform_requirements', 'parent_uid']:
            if k in metadata:
                del metadata[k]

        return self.T.create_entry('course_file', cfrecord['uid'], metadata)

    def _generate_tracking_title(self, courseware, title):
        return u"{}.{} - {}".format(
            courseware.fields()['department_number'], 
            courseware.fields()['master_course_number'], 
            title
        )

    def _create_course_page(self, cprecord, courseware):
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
    
        :param cprecord: JSON record with course file metadata (sparse)
        :return: Contentful Entry for the course file 
        """
        metadata = dict((k,cprecord[k]) for k in cprecord.keys() if isinstance(cprecord[k], unicode)==True)
        metadata['tracking_title'] = self._generate_tracking_title(courseware, cprecord['title'])
        for k in ['uid']:
            del metadata[k]

        metadata['course_page_type'] = metadata.pop('type')
        return self.T.create_entry('course_page', cprecord['uid'], metadata)

    def _create_course_embedded_media(self, emrecord, courseware):
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
        metadata = dict((k,emrecord[k]) for k in emrecord.keys() if isinstance(emrecord[k], unicode)==True)
        added_meta = {
            u'tracking_title': self._generate_tracking_title(courseware, emrecord['title']),
            u'courseware': [courseware],
        }
        metadata.update(added_meta)
        return self.T.create_entry('embedded_media', emrecord['uid'], metadata)

    def add_courseware(self, ocw_url):
        """
        Main routine to add a single course from OCW to Contentful.
        """
        #Grab the single course record from OCW JSON data
        record = self.get_courseware_metadata(ocw_url)

        #Step 1: create the basic metadata for a courseware entry in Contentful
        courseware = self._create_courseware(record)

        #Step 2: add department
        department = self._create_department(self.departments[record['department_number']])
        courseware.department = [department]
        courseware.save()

        #Step 3: iterate over the faculty list; create if does not exist, link to courseware
        flinks = []
        for f in record['instructors']:
            flinks.append(self._create_instructor(f))
        
        courseware.instructors = [fl for fl in flinks] # Update new_courseware with faculty clinks
        courseware.save()

        #Step 4: iterate through course tags and attach to courseware
        tlinks = []
        for t in record['tags']:
            t['name'] = t['name']#.encode("utf8","ignore")
            tlinks.append(self._create_tag(t))

        courseware.tags = [tl for tl in tlinks] # Update new_courseware with tag clinks
        courseware.save()

        #Step 5: iterate through course pages and attach to courseware
        cplinks = []
        for cp in record['course_pages']:
            cplinks.append(self._create_course_page(cp, courseware))

        courseware.course_pages = [cpl for cpl in cplinks]
        courseware.save()

        #Step 6: iterate through course files and attach courseware
        cflinks = defaultdict(list)
        allcflinks = []
        for cf in record['course_files'][0:30]:
            tmp_cf = self._create_course_file(cf, courseware)
            cflinks[cf['parent_uid']].append(tmp_cf)
            allcflinks.append(tmp_cf)

        courseware.course_files = allcflinks
        courseware.save()

        for key in cflinks:
            try:
                course_page = client.entries(sid, eid).find(key)
                course_page.files = cflinks[key]
                course_page.save()
            except:
                print("Page not found: {}".format(key))
            
        # courseware.course_files = [cfl for cfl in cflinks] # Update new_courseware with course file clinks
        # courseware.save()

        #Step 7: iterate through embedded media, create entries, and attach to course page 
        emlinks = defaultdict(list)
        for key in record['course_embedded_media']:
            page = record['course_embedded_media'][key]
            em = {r['id']: r['media_info'][0:200] for r in page['embedded_media'] if r["id"]=="Video-YouTube-Stream"}
            page.update(em)
            page['technical_location'] = page['technical_location'][0:250]
            del page['embedded_media']
            emlinks[page['parent_uid']].append(self._create_course_embedded_media(page, courseware))

        for key in emlinks:
            try:
                course_page = client.entries(sid, eid).find(key)
                course_page.files = emlinks[key]
                course_page.save()
            except:
                print("Page not found: {}".format(key))

        # #Step 8: associate files and media with specific course pages
        # for key in cflinks:
        #     course_page = client.entries(sid, eid).find(key)
        #     course_page.files = cflinks[key]
        #     course_page.save()

        return courseware


if __name__ == "__main__":
    '''
    Examples of populating a Contentful space with OCW content.
    '''
    from pprint import pprint
    import urllib

    OCW = Ocw2Contentful()
    # url = 'https://ocw.mit.edu/courses/aeronautics-and-astronautics/16-01-unified-engineering-i-ii-iii-iv-fall-2005-spring-2006/'
    # url = 'https://ocw.mit.edu/courses/physics/8-01sc-classical-mechanics-fall-2016/'
    # url = 'https://ocw.mit.edu/courses/civil-and-environmental-engineering/1-050-solid-mechanics-fall-2004'
    # url = 'https://ocw.mit.edu/courses/mathematics/18-06-linear-algebra-spring-2010'
    # url = 'https://ocw.mit.edu/courses/mathematics/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/'
    # url = 'https://ocw.mit.edu/courses/biology/7-13-experimental-microbial-genetics-fall-2008/'
    # url = 'https://ocw.mit.edu/courses/physics/8-591j-systems-biology-fall-2014/'
    # url = 'https://ocw.mit.edu/courses/materials-science-and-engineering/3-024-electronic-optical-and-magnetic-properties-of-materials-spring-2013/'
    url = 'https://ocw.mit.edu/courses/physics/8-06-quantum-physics-iii-spring-2005/'
    c = OCW.add_courseware(url)
    print("Success creating courseware: {}".format(c))

    # OCW = Ocw2Contentful()
    # counter = 0
    # for k,v in OCW.departments.iteritems():
    #     if counter < 10: 
    #         dept_url = "https://ocw.mit.edu/courses/{}/{}.json".format(v['id'], v['id'])
    #         dept_data = json.loads(urllib.urlopen(dept_url).read())
    #         course_record = dept_data[2]
    #         course_url = course_record[course_record.keys()[0]]['course_path']
    #         print("Parsing: {}".format(course_url))
    #         c = OCW.add_courseware(course_url)
    #         print("Success creating courseware: {}".format(c))
    #         counter = counter + 1
    