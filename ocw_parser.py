import json
import urllib


import json
import urllib
from pprint import pprint

class OCW(object):
    def __init__(self, department_url):
        """
        JSON data is organized by department. Each department has a list of courses with
        metadata and file links nested by type. In order to get to a single course, we 
        start with the department JSON, then loop through each course. So we start by 
        loading all data for a given department.

        :param department_url: OCW endpoint for deparment JSON data (e.g., https://ocw.mit.edu/courses/biology/biology.json)
        jdata: json data returned from the input url

        Future work: automatically grab department Contentful ID
        """
        self.department_url = department_url
        self.jdata = json.loads(urllib.urlopen(department_url).read())
        
        #Munge department data so ocw uid are directly the keys of the json data
        #Will allow us to parse one course at a time, or reparse a course to make updates/fix
        jdata = json.loads(urllib.urlopen(department_url).read())
        self.jdata = dict((v.keys()[0], v[v.keys()[0]]) for v in jdata)
        
        print("Parsing the following OCW endpoint: {}".format(department_url))
    
    def parse_course(self, ocw_uid):
        """
        ocw_uid: unique key identifying specific course within the course_datum; created by OCW
        course_datum: a nested json object containing all relevant metadata and content links
        :return: pd.DataFrame with course IDs as indices and metadata as columns
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
        return len(entry[k])
    
    def _pdf_list(self, entry, k):
        return len(entry[k])


if __name__ == "__main__":
    '''
    Example of parsing through a department in order to create course records.
    Fundamentally, we need to start by creating courses, then creating and 
    associating other entries with the course.

    For example, parse the course, create in Contentful, then go back 
    through faculty, create if they do not exist, and associate with course.

    '''
    department = OCW('https://ocw.mit.edu/courses/physics/physics.json')
    for course_datum in department.jdata[slice(0,2)]:
        record = department.parse_course(course_datum)
        print(record)
