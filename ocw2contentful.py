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
        :deparment_clink_id: Contentful Department Entry ID 
        """
        self.OCW = OCW(department_url)
        self.department_clink_id = department_clink_id
        self.T = Translate('1c5BaHz1xsxiNogsMkMQPr')


    def _generate_courseware_uid(self, record):
        # unique id assigned in contentful (length 1 to 64 characters); ocw uids are too long
        return '__'.join(['OCW', record['master_course_number'], record['year'], record['term']])        
        
    def _make_camel(self, string):
        return ''.join(x for x in string.title() if x.isalnum())
    
    def _create_courseware(self, ocw_uid, record):
        """
        :param record: OCW json data for a given ocw_uid
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
        Given a faculty name from OCW data, create the entry if it does not exist. Prof and Dr distinguish
        between faculty and instructors (other).
            Prof. Krishna Rajagopal
            Dr. Saif Rayyan
        :param faculty_name: str name formatted in a typical way (Dr. Daniel Seaton)
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
        Original Format (we extract unique values, create if the don't exist, and update links to courseware):
                    {u'speciality': u'Astrophysics',
                     u'subtopic': u'Physics',
                     u'topic': u'Science'},
                    {u'speciality': u'Theoretical Physics',
                     u'subtopic': u'Physics',
                     u'topic': u'Science'}
        
        :param content_type: the content_type name from Contentful. Set up to take 0 index of unique tuple.        
        :param topic_set: value to be put in tag.
        :return: Contentful Entry for the tag content type [Topic, Subtopic, or Speciality]
        """
        contentful_uid = self._make_camel(tag_value)
        # tag_type = getattr(self, content_type+'_type')
        tag_meta = {'title': tag_value}

        return self.T.create_entry(content_type_name, contentful_uid, tag_meta)

    def add_courseware(self, ocw_uid):
        """
        Main routine to add a single course from OCW to Contentful.
        """
        # Grab the single course record from OCW JSON data
        record = self.OCW.parse_course(ocw_uid)

        # Step 1: create the basic metadata for a courseware entry in Contentful
        courseware = self._create_courseware(ocw_uid, record)
        print("Success!: {} ({})".format(courseware, ocw_uid))
        
        # Step 2: iterate over the faculty list; create if does not exist, link to courseware
        flinks = []
        for f in record['faculty']:
            flinks.append(self._create_instructor(f))
        
        # Update new_courseware with faculty clinks
        courseware.instructors = [fl for fl in flinks]
        
        # # Step 3: iterate through course_topics 
        # #     identify the unique ones (attempt to save API calls)
        # #     create if does not exist, link to courseware
        # uniq_ctopics = {'topic': [], 'subtopic': [], 'speciality': []}
        # save_ctopics = {}
        
        # for topic_sets in record['course_topics']:
        #     for k,v in topic_sets.iteritems():
        #         if (k,v) not in save_ctopics:
        #             uniq_ctopics[k].append(self._create_tag(k, v))
        #             save_ctopics[(k,v)] = True

        # for k in uniq_ctopics:
        #     setattr(courseware, k, uniq_ctopics[k])
        
        courseware.save()
        return courseware


if __name__ == "__main__":
    '''
    Example of populating a Contentful space with a single OCW course.
    '''
    tmp = Ocw2Contentful('https://ocw.mit.edu/courses/physics/physics.json', '1c5BaHz1xsxiNogsMkMQPr')
    tmp.add_courseware('8-286-the-early-universe-fall-2013') # single instructor, minimal tags
    # tmp.add_courseware('8-01sc-classical-mechanics-fall-2016') # 5 instructors, lots of tags
