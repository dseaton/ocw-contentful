# Adapted from https://medium.com/grammofy/testing-your-python-api-app-with-json-schema-52677fe73351
import json
from os.path import join, dirname
import sys
sys.path.append('../')

from jsonschema import validate


def assert_valid_schema(data, schema_file):
    """ Checks whether the given data matches the schema """

    schema = _load_json_schema(schema_file)
    return validate(data, schema)


def _load_json_schema(filename):
    """ Loads the given schema file """

    relative_path = join('schemas', filename)
    absolute_path = join(dirname(__file__), relative_path)

    with open(absolute_path) as schema_file:
        return json.loads(schema_file.read())

def test_courseware(courseware_json_record):
    assert_valid_schema(courseware_record, 'courseware.json')

if __name__ == "__main__":
    '''
    Running tests on a single courseware.
    '''
    from pprint import pprint
    from ocw_parser import OCW
    

    dept = 'biology'
    tmp = OCW('https://ocw.mit.edu/courses/{}/{}.json'.format(dept, dept))
    
    ### Test one courseware
    courseware_record = tmp.jdata['7-344-tumor-suppressor-gene-p53-how-the-guardian-of-our-genome-prevents-cancer-fall-2010']
    try:
        test_courseware(courseware_record)
    except Exception as e:
        print(e)

    ### Test multiple coursewares
    for cuid in tmp.jdata.keys():
        print(cuid)
        pprint(tmp.jdata[cuid]['course_topics'])
        # # test_courseware(tmp.jdata[cuid])
        # try:
        #     test_courseware(tmp.jdata[cuid])
        #     print("Success")
        # except Exception as e:
        #     print(e)
    
