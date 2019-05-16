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
    
    def new_create_entry(self, content_type_name, entry_uid, entry_attributes):
        """
        Return a Contentful Entry from OCW input data. If entry exists, returns Entry without creating or updating.   
        For non-existent Entries, metadata are added based on their types and found in the _set_field_type function.
        unicode: text field
        contentful class: single reference field
        list: multi-reference field
        
        When calling create_entry(), provide the following parameters:

        :param content_type_name: str used to identify Contentful content_type. Convention: {content_type_name}_type.
        :param entry_uid: the entry's unique Contentful ID (we attempt to use OCW UIDs as much as possible).
        :param entry_attributes: dict containing metadata that will be mapped to Contentful.
        :param force_creation: default None, intended to force creation when needing to change/update an existing Entry.
        :return: Contentful Entry object.
        """

        # Return the entry if the entry_uid already exists in Contentul 
        try:
            return self.entries_client.find(entry_uid)
        except:
            # print(type(content_type_name), type(str(entry_uid.encode)))
            print "Creating {}: {}".format(content_type_name, entry_uid)
        
        # Create the entry and return 
        return self.entries_client.create(
            entry_uid, 
            getattr(self, content_type_name)(entry_attributes) # naming convention required
        )

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
            # print(type(content_type_name), type(str(entry_uid.encode)))
            print "Creating {}: {}".format(content_type_name, entry_uid)
        
        # Create the entry and return 
        return self.entries_client.create(
            entry_uid, 
            getattr(self, content_type_name)(entry_attributes) # naming convention required
        )

    def courseware(self, entry_attributes):
        return { 
            'content_type_id': 'courseware',
            'fields': {self.to_camel_case(e): self._set_field_type(v) for e,v in entry_attributes.iteritems()}
        }

    def instructor(self, entry_attributes):
        return { 
            'content_type_id': 'instructor',
            'fields': {self.to_camel_case(e): self._set_field_type(v) for e,v in entry_attributes.iteritems()}
        }
    
    def tag(self, entry_attributes):
        return {
            'content_type_id': 'tag',
            'fields': {self.to_camel_case(e): self._set_field_type(v) for e,v in entry_attributes.iteritems()}
        }

    def department(self, entry_attributes):
        return {
            'content_type_id': 'department',
            'fields': {self.to_camel_case(e): self._set_field_type(v) for e,v in entry_attributes.iteritems()}
        }

    def course_page(self, entry_attributes):
        return {
            'content_type_id': 'coursePage',
            'fields': {self.to_camel_case(e): self._set_field_type(v) for e,v in entry_attributes.iteritems()}
        }

    def course_file(self, entry_attributes):
        return {
            'content_type_id': 'courseFile',
            'fields': {self.to_camel_case(e): self._set_field_type(v) for e,v in entry_attributes.iteritems()}
        }

    def embedded_media(self, entry_attributes):
        return {
            'content_type_id': 'embeddedMedia',
            'fields': {self.to_camel_case(e): self._set_field_type(v) for e,v in entry_attributes.iteritems()}
        }

    def _set_field_type(self, v):
        if isinstance(v, unicode):
            return self._text_field(v)
        elif isinstance(v, contentful_management.entry.Entry):
            return self._single_reference_field(v.sys['id'])
        elif isinstance(v, list):
            return self._multi_reference_field([l.sys['id'] for l in v])
        else:
            return None

    def _text_field(self, value):
        if value!='':
            return {'en-US': value}
        else:
            return None
    
    def _single_reference_field(self, value):
        return {'en-US': self._sys_field(value)}
    
    def _multi_reference_field(self, list_values):
        return {'en-US': [self._sys_field(v) for v in list_values]}
    
    def _sys_field(self, cid):
        '''
        param cid: contentful id
        '''
        return {'sys': {'type': 'Link', 'linkType': 'Entry', 'id': cid}}

    def to_camel_case(self, string):
        components = string.replace('-','_').split('_')
        return components[0] + ''.join(x.title() for x in components[1:])
    

if __name__ == "__main__":
    from pprint import pprint
    
    # Example using the Contentful client
    client = contentful_management.Client(secure.MANAGEMENT_API_TOKEN)
    sid = secure.SPACE_ID
    eid = secure.ENVIRONMENT_ID
    content_type = client.content_types(sid, eid).find('instructor')

    # Translation of metadata to a Contentful entry
    T = Translate()
    pprint(
        T.autoInstructor({
            'name': 'Daniel Seaton', 
            'title': 'Dr.', 
            'bio': 'New at ODL.',
            'department_clink_id': '1c5BaHz1xsxiNogsMkMQPr'
        })
    )
