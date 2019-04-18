from pprint import pprint

import contentful_management

from contentful_mapping import Translate
from ocw_parser import OCW
import secure


client = contentful_management.Client(secure.MANAGEMENT_API_TOKEN)
sid = secure.SPACE_ID
eid = secure.ENVIRONMENT_ID

class Ocw2Contentful(object):        
    def __init__(self, department_url, department_clink_id):
        """
        :param department_url: OCW url pointing to JSON department data; used to init ocw_parser
        :param deparment_clink_id: Contentful Department Entry ID 
        """
        self.OCW = OCW(department_url)
        self.department_clink_id = department_clink_id
        self.T = Translate()


    def _generate_courseware_uid(self, record):
        """
        Assign a unique ID for new entry in Contentful (length 1 to 64 characters); ocw uids are too long.
        :param record: JSON data for single course. 
        :return: unique ID made up of course metadata.
        """
        return '__'.join(['OCW', record['master_course_number'], record['year'], record['term'].strip()])        
        
    def _make_camel(self, string):
        return ''.join(x for x in string.title() if x.isalnum())
    
    def _create_courseware(self, ocw_uid, record):
        """
        Create an autoCourseware entry inside Contentful space. Does not create if the
        entry already exists.

        :param ocw_uid: unique identifier found in OCW JSON data (keys of department data)
        :param record: OCW json data for a given for a single course
        :return: Contentful Entry for autocourseware content type
        """ 
        contentful_uid = self._generate_courseware_uid(record)
        
        # Create basic/minimum metadata needed to create a courseware entry in Contentful 
        courseware_meta = dict((k,record[k]) for k in record.keys() if isinstance(record[k], unicode)==True)
        added_meta = {
            'course_uid': ocw_uid,
            'department_clink_id': self.department_clink_id,
            'tracking_title': "{} - {}".format(record['master_course_number'], record['course_title']),
        }
        courseware_meta.update(added_meta)
        return self.T.create_entry('autoCourseware', contentful_uid, courseware_meta)
        
    def _create_instructor(self, faculty_name):
        """
        Create an autoInstructor entry inside Contentful space. Does not create if the
        entry already exists. Typical entry looks like:
            Example 1: Prof. Krishna Rajagopal
            Example 2: Dr. Saif Rayyan
        
        :param faculty_name: str name formatted in a typical way (Dr. Saif Rayyan)
        :return: Contentful Entry for instructor content type 
        """
        contentful_uid = self._make_camel(faculty_name)
        instructor_meta = {
            'department_clink_id': self.department_clink_id,
            'name': faculty_name.split('.')[1] if '.' in faculty_name else faculty_name,
            'title': faculty_name.split('.')[0] if '.' in faculty_name else None,
        }
        return self.T.create_entry('autoInstructor', contentful_uid, instructor_meta)

    def _create_tag(self, content_type_name, tag_value):
        """
        Current OCW tagging hierarchy: Topic -> Subtopic -> Speciality
        In Contentful, created content_types for each with multi-references.
        Original Format (we extract unique values, create if do not exist, and update links to courseware):
                    {u'speciality': u'Astrophysics',
                     u'subtopic': u'Physics',
                     u'topic': u'Science'},
                    {u'speciality': u'Theoretical Physics',
                     u'subtopic': u'Physics',
                     u'topic': u'Science'}
        
        :param content_type_name: the content_type name from Contentful.        
        :param tag_value: value to be put in tag.
        :return: Contentful Entry for the tag content type [Topic, Subtopic, or Speciality]
        """
        contentful_uid = self._make_camel(tag_value)
        tag_meta = {'title': tag_value}

        return self.T.create_entry(content_type_name, contentful_uid, tag_meta)

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

    def _create_pdf_resource(self, pdf_path, pdf_type, subtopic, courseware_uid):
        """
        OCW pdf resources are organized by type and listed as direct urls:
        u'pdf_list': {
            u'assignments': [
                u'https://ocw.mit.edu/courses/physics/8-286-the-early-universe-fall-2013/assignments/MIT8_286F13_ps9.pdf',
                u'https://ocw.mit.edu/courses/physics/8-286-the-early-universe-fall-2013/assignments/MIT8_286F13_ps3.pdf',
                ...
                ],
                u'exams': [
                    u'https://ocw.mit.edu/courses/physics/8-286-the-early-universe-fall-2013/exams/MIT8_286F13_q1.pdf',
                    u'https://ocw.mit.edu/courses/physics/8-286-the-early-universe-fall-2013/exams/MIT8_286F13_q3review.pdf',
                    ...
                ],
                u'lecture-slides': [
                   u'https://ocw.mit.edu/courses/physics/8-286-the-early-universe-fall-2013/lecture-slides/MIT8_286F13_lec12.pdf',
                   u'https://ocw.mit.edu/courses/physics/8-286-the-early-universe-fall-2013/lecture-slides/MIT8_286F13_lec19.pdf',
                ],
                ...
            ]
        }
        :param pdf_path: url location of a given pdf file. 
        :param pdf_type: refers to OCW designations of course structure (exams, assignments, lecture-slides, etc).
        :param sub_topic: subtopic for a given courseware, so user gets an idea of topic for a pdf in Contentful.
        :param courseware_uid: Contentful unique id that lets us associate a course with this tag.
        :return: mediaResource entry from Contentful.
        """
        contentful_uid = pdf_path.split('/')[-1]

        p_meta = {
            'courseware': courseware_uid,
            'path': pdf_path,
            'pdf_type': pdf_type,
            'subtopic': subtopic,
            'tracking_title': contentful_uid,
        }
        return self.T.create_entry('pdfResource', contentful_uid, p_meta)

    def add_courseware(self, ocw_uid):
        """
        Main routine to add a single course from OCW to Contentful.
        """
        # Grab the single course record from OCW JSON data
        record = self.OCW.parse_course(ocw_uid)

        # Step 1: create the basic metadata for a courseware entry in Contentful
        courseware = self._create_courseware(ocw_uid, record)

        # Step 2: iterate over the faculty list; create if does not exist, link to courseware
        flinks = []
        for f in record['faculty']:
            flinks.append(self._create_instructor(f))
        
        courseware.instructors = [fl for fl in flinks] # Update new_courseware with faculty clinks
        courseware.save()

        # Step 3: iterate through course_topics 
        #     identify the unique ones (attempt to save API calls)
        #     create if does not exist, link to courseware
        uniq_ctopics = {'topic': [], 'subtopic': [], 'speciality': []}
        save_ctopics = {}
        
        for topic_sets in record['course_topics']:
            for k,v in topic_sets.iteritems():
                if (k,v) not in save_ctopics and v!='':
                    uniq_ctopics[k].append(self._create_tag(k, v))
                    save_ctopics[(k,v)] = True

        for k in uniq_ctopics:
            setattr(courseware, k, uniq_ctopics[k])
        courseware.save()

        #Step 4: iterate through media resources; create if does not exist, link to courseware
        mlinks = []
        for m in record['media_resources'][slice(0,4)]:
            mlinks.append(self._create_media_resource(m, getattr(courseware, 'id')))

        courseware.media_resources = [ml for ml in mlinks] # Update courseware with media links
        courseware.save()

        #Step 5: iterate through pdf list; create if does not exist, link to courseware
        for ptype in ['assignments', 'exams']:
            if ptype in record['pdf_list']:
                plinks = []
                for path in record['pdf_list'][ptype][slice(0,4)]:
                    plinks.append(
                        self._create_pdf_resource(
                            path, 
                            ptype, 
                            getattr(uniq_ctopics['subtopic'][0], 'id'), 
                            getattr(courseware, 'id')
                        )
                    )

                setattr(courseware, ptype, [pl for pl in plinks])
        courseware.save()
        
        courseware.publish()
        return courseware


if __name__ == "__main__":
    '''
    Examples of populating a Contentful space with OCW content.
    '''
    ### Testing single courses
    # dept = 'physics'
    # cuid = '8-286-the-early-universe-fall-2013'
    # url = 'https://ocw.mit.edu/courses/{}/{}.json'.format(dept, dept)
    # tmp = Ocw2Contentful(url, secure.departments[dept])
    # record = tmp.OCW.parse_course(cuid)
    # print(record)
    # # tmp.add_courseware(cuid) # single instructor, minimal tags

    ### Test loading multiple courses across multiple departments
    for k,v in secure.departments.iteritems():
        tmp = Ocw2Contentful('https://ocw.mit.edu/courses/{}/{}.json'.format(k, k), v)
        for cuid in tmp.OCW.jdata.keys()[slice(0,3)]:
            print(cuid)
            # tmp.add_courseware(cuid)
            print('\n')
