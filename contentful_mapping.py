'''
Stores the content model mappings we populate with OCW content.
'''
import contentful_management

import secure


class Translate(object):
    def __init__(self):
        '''
        Must be called with a department already set.
        '''        
        self.client = contentful_management.Client(secure.MANAGEMENT_API_TOKEN)
        self.entries_client = self.client.entries(secure.SPACE_ID, secure.ENVIRONMENT_ID)
        self.content_types_client = self.client.content_types(secure.SPACE_ID, secure.ENVIRONMENT_ID)
        return None
    
    def create_entry(self, content_type_name, entry_uid, entry_attributes):
        """
        Generalizing the entry creation process for OCW to Contentful. 
        Step 1: Try to get the entry for content_type and entry_uid.
        Step 2: if does not exist, try to create the entry of type content_type_name with entry_uid and entry_attributes.
        :param content_type_name: str used to identify Contentful content_type. Convention: {content_type_name}_type
        :param entry_uid: the entry's unique id in Contentful
        :param entry_attributes: dict containing metadata that will be mapped to Contentful.
        """

        # Return the entry if the entry_uid already exists in Contentul 
        try:
            return self.entries_client.find(entry_uid)
        except:
            print("Creating {}: {}".format(content_type_name, entry_uid))
        
        # Create the entry and return 
        return self.entries_client.create(
            entry_uid, 
            getattr(self, content_type_name)(entry_attributes) # naming convention required
        )
    
    def pdfResource(self, lookup):
        return {
            'content_type_id': 'pdfResource',
            'fields': {
                'courseware': self._multi_reference_field([lookup['courseware']]),
                'path': self._text_field(lookup['path']),
                'subtopic': self._multi_reference_field([lookup['subtopic']]),
                'trackingTitle': self._text_field(lookup['tracking_title']),
                'pdfType': self._text_field(lookup['pdf_type']),
            }
        }

    def mediaResource(self, lookup):
        return {
            'content_type_id': 'mediaResource',
            'fields': {
                'path': self._text_field(lookup['path']),
                'title': self._text_field(lookup['title']),
                'youTubeId': self._text_field(lookup['youtube_id']),
                'courseware': self._multi_reference_field([lookup['courseware']]),
            }
        }

    def topic(self, lookup):
        return {
            'content_type_id': 'topic',
            'fields': {
                'title': self._text_field(lookup['title']),
            }
        }

    def subtopic(self, lookup):
        return {
            'content_type_id': 'subtopic',
            'fields': {
                'title': self._text_field(lookup['title']),
            }
        }

    def speciality(self, lookup):
        return {
            'content_type_id': 'speciality',
            'fields': {
                'title': self._text_field(lookup['title']),
            }
        }

    def autoInstructor(self, lookup):
        return { 
            'content_type_id': 'autoInstructor',
            'fields': {
                'name': self._text_field(lookup['name']),
                'title': self._text_field(lookup['title']),
                'department': self._multi_reference_field([lookup['department_clink_id']]),
                'bio': None,
                'courseware': None,
            }
        }
    
    def autoCourseware(self, lookup):
        return { #[faculty for faculty in course_info['faculty']]
            'content_type_id': 'autoCourseware',
            'fields': {
                'trackingTitle': self._text_field(lookup['tracking_title']),
                'courseTitle': self._text_field(lookup['course_title']),
                'courseImage': None,
                'courseImagePath': self._text_field(lookup['course_image_path']),
                'department': self._multi_reference_field([lookup['department_clink_id']]),
                'description': None,
                'plainTextDescription': self._text_field(lookup['description']),
                'courseUid': self._text_field(lookup['course_uid']),
                'term': self._text_field(lookup['term']),
                'year': self._text_field(lookup['year']),
                'level': self._text_field(lookup['level']),
                'masterCourseNumber': self._text_field(lookup['master_course_number']),
                'coursePath': self._text_field(lookup['course_path']),
                'instructors': None,
                'keywords': None,
                'mediaResources': None,
            }
        }
    
    def _text_field(self, value):
        return {'en-US': value}
    
    def _single_reference_field(self, value):
        return {'en-US': self._sys_field(value)}
    
    def _multi_reference_field(self, list_values):
        return {'en-US': [self._sys_field(v) for v in list_values]}
    
    def _sys_field(self, cid):
        '''
        param cid: contentful id
        '''
        return {'sys': {'type': 'Link', 'linkType': 'Entry', 'id': cid}}
    

if __name__ == "__main__":
    import contentful_management
    from pprint import pprint
    import secure
    
    # Example use for creating an instructor
    client = contentful_management.Client(secure.MANAGEMENT_API_TOKEN)
    sid = secure.SPACE_ID
    eid = secure.ENVIRONMENT_ID
    content_type = client.content_types(sid, eid).find('instructor')

    T = Translate()
    pprint(
        T.autoInstructor({
            'name': 'Daniel Seaton', 
            'title': 'Dr.', 
            'bio': 'New at ODL.',
            'department_clink_id': '1c5BaHz1xsxiNogsMkMQPr'
        })
    )
