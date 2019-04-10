'''
Stores the content model mappings we populate with OCW content.
'''

class Translate(object):
    def __init__(self, content_type, department_clink_id):
        '''
        Must be called with a department already set.
        '''
        
        self.content_type = content_type
        self.department_clink_id = department_clink_id
        return None
    
    def topic_tag(self, **kwargs):
        ids = [f.id for f in self.content_type.fields] 
        lookup = dict((i, kwargs.get(i, None)) for i in ids)
        print(self.content_type)
        return {
            'content_type_id': getattr(self.content_type, 'id'),
            'fields': {
                'title': self._text_field(lookup['title']),
            }
        }
    
    def instructor(self, **kwargs):
        ids = [f.id for f in self.content_type.fields]
        lookup = dict((i, kwargs.get(i, None)) for i in ids)
        
        return { 
            'content_type_id': 'autoInstructor',
            'fields': {
                'name': self._text_field(lookup['name']),
                'title': self._text_field(lookup['title']),
                'department': self._multi_reference_field([self.department_clink_id]),
                'bio': self._text_field(lookup['bio']),
                'courseware': None,
            }
        }
    
    def courseware(self, **kwargs):
        ids = [f.id for f in self.content_type.fields]
        lookup = dict((i, kwargs.get(i, None)) for i in ids)
        
        return { #[faculty for faculty in course_info['faculty']]
            'content_type_id': 'autoCourseware',
            'fields': {
                'trackingTitle': self._text_field(lookup['tracking_title']),
                'courseTitle': self._text_field(lookup['course_title']),
                'courseImage': None,
                'courseImagePath': self._text_field(lookup['course_image_path']),
                'department': self._multi_reference_field([self.department_clink_id]),
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
    import secure
    
    # Example use for creating an instructor
    client = contentful_management.Client(secure.MANAGEMENT_API_TOKEN)
    sid = secure.SPACE_ID
    eid = secure.ENVIRONMENT_ID
    content_type = client.content_types(sid, eid).find('instructor')

    T = Translate(content_type)
    new_entry = client.entries(sid, eid).create(
        'danielSeaton',
        T.instructor(name='Daniel Seaton', title='Dr.', bio='New at ODL.')
    )
