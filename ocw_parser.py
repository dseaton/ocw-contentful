import json
import urllib


class OCW(object):
    def __init__(self, department_url):
        """
        OCW provides courseware data in a JSON format organized by department. Each 
        department has a list of courses with metadata and file links  nested by type. 
        In order to get to a single course, we load the department data, then access a 
        single course (ocw uids are keys) or loop through courses. Department URL
        example:  https://ocw.mit.edu/courses/biology/biology.json

        :param department_url: OCW endpoint for deparment JSON data 
        
        Attributes
        ----------
        :department_url: OCW endpoint used to initiate object
        :jdata: json data returned from the input url

        Future work: automatically grab department Contentful ID
        """
        self.department_url = department_url
        
        #Munge department data so ocw uid are directly the keys of the json data
        #Will allow us to parse one course at a time, or reparse a course to make updates/fix
        jdata = json.loads(urllib.urlopen(department_url).read())
        self.jdata = dict((v.keys()[0], v[v.keys()[0]]) for v in jdata)

        print("Parsing the following OCW endpoint: {}".format(department_url))

    def parse_course(self, ocw_uid):
        """
        Given a specific ocw_uid, visitor pattern iteration through each object within 
        the nested json. If the object type is not specified as a parsing function, parsing
        falls back to  _default. 
        
        Current implementation is admittedly bare. Considering moving transformation code 
        from ocw2contentful.py to each parsing function.

        :param ocw_uid: unique key identifying specific course within the course_datum; created by OCW
        :param course_datum: a nested json object containing all relevant metadata and content links for a single course
        :returns: json data representing transformation of course_datum 
        """
        course_datum = self.jdata[ocw_uid]
        
        record = dict()
        for k in course_datum:
            parse = getattr(self, '_' + k, self._default)
            record[k] = parse(course_datum, k)
        
        return record
    
    def _get_element(self, entry, key, default=None):
        value = entry.get(key, '_default')
        if value:
            return value
        return default
    
    def _default(self, entry, k):
        return entry[k]

    def _course_section_and_tlp_urls(self, entry, k):
        return entry[k]

    def _course_topics(self, entry, k):
        return entry[k]

    def _faculty(self, entry, k):
        return entry[k]

    def _media_resources(self, entry, k):
        return entry[k]
    
    def _pdf_list(self, entry, k):
        return entry[k]


if __name__ == "__main__":
    """
    Example of parsing a single course from the physics department.
    """
    from pprint import pprint

    department = OCW('https://ocw.mit.edu/courses/physics/physics.json')
    record = department.parse_course('8-286-the-early-universe-fall-2013')
    pprint(record)
