# from django.test import TestCase
import requests
# from django.utils.timezone import utc
# Create your tests here.

# default=datetime.datetime(2019, 8, 23, 17, 59, 40, 153036, tzinfo=utc)

# url = 'http://localhost:8006/api/v1/crs/'
# url = 'https://test.cpims.net/api/v1/crs/'
url = 'https://childprotection.go.ke/api/v1/crs/'
# headers = {'Authorization': 'Token 330764ede3eb59acca76b8f064b84eb477ff452e'}


data = {'physical_condition': 'PNRM', 'county': '40', 'sub_county_code': '228', 'hh_economic_status': 'UINC', 'other_condition': 'CHNM', 'child_sex': 'SMAL', 'reporter_first_name': 'Morgan', 'ob_number': '', 'longitude': None, 'recommendation_bic': "1.Child received PSS session from childline Kenya . \n2.Child's home to be traced and reintegration done. \n3.Child to be enrolled back to school.\n4The case was escalated at the Busia SC DCS officer", 'family_status': 'FSLA', 'reporter_other_names': '', 'case_date': '2025-11-16', 'child_other_names': '', 'friends': None, 'organization_unit': 'Helpline 116', 'case_reporter': 'CRHE', 'child_in_school': '0', 'tribe': '', 'sublocation': '1141', 'child_surname': 'Omondi', 'case_village': 'Unknown Village', 'latitude': None, 'child_first_name': 'Morgan', 'reporter_telephone': '254722478040', 'court_number': '', 'verification_status': '001', 'child_dob': '2008-11-15', 'perpetrator_status': 'PKNW', 'reporter_surname': 'Omondi', 'case_narration': "Date of incident 2025-10-09 . Morgan Omondi walked in to report a case where in January 2025 he was recruited by Benjamin Ouma from Mujuru village in Busia and taken to Kitale to be a Child Domestic Worker cleaning the home and doing farm work for a person called Aaron. He reported performing heavy tasks but was never paid and he was also not attending school. The child requests support to attend vocational college and learn mechanics. He is currently staying at Busia Compassionate Children's Home (Stella Egesa - 0722478040) in Mayenje, Busia County, placed there by DCS after being rescued from Mary Gladys Rescue Center which was shut down by NCCS due to mistreatment of children. He had been in the home since a tender age and does not know his home.\n", 'court_name': '', 'case_landmark': "Mayenje At Busia Compassionate Children's Home", 'religion_type': None, 'long_term_needs': None, 'immediate_needs': None, 'mental_condition': 'MNRM', 'police_station': '', 'risk_level': 'RLMD', 'constituency': '228', 'hobbies': None, 'reporter_email': '', 'location': '1141', 'reporter_county': '40', 'reporter_sub_county': '228', 'reporter_ward': '1141', 'reporter_village': 'UNK', 'has_birth_cert': None, 'user': 'BAKARII', 'area_code': '40', 'case_category_id': 'CTRF', 'case_category': 'Child Labour', 'case_details': [{'place_of_event': 'PECE', 'category': 'CTRF', 'sub_category': 'LBDW', 'nature_of_event': 'OOEV', 'date_of_event': '2026-03-16'}], 'categories': [{'case_category': 'CTRF', 'case_sub_category': 'LBDW', 'case_date_event': '2026-03-16', 'case_nature': 'OOEV', 'case_place_of_event': 'PECE', 'case_id': '319616'}], 'perpetrators': [{'first_name': 'Benjamin', 'surname': 'Ouma', 'relationship': '^Stranger', 'sex': 'SMAL'}], 'siblings': [{'surname': 'Omondi', 'dob': '2008-11-15', 'sex': 'SMAL', 'school_name': '', 'other_names': '', 'first_name': 'Morgan', 'class': '', 'remarks': ''}], 'parents': [{}, {}], 'caregivers': []}

datas = {"county": "001", "constituency": "001", "case_category": "CDIS",
        "child_dob": "2010-06-15", "perpetrator": "PKNW",
        "child_first_name": "Susan", "child_surname": "Atieno",
        "case_landmark": "Near kiroboto primary",
        "case_narration": "Child was abducted", "child_sex": "SMAL",
        "reporter_first_name": "Mark", "reporter_surname": "Masai",
        "reporter_telephone": "254722166058",
        "reporter_county": "001", "reporter_sub_county": "001",
        "case_reporter": "CRSF", "organization_unit": "Helpline",
        "hh_economic_status": "UINC", "family_status": "FSUK",
        "mental_condition": "MNRM", "physical_condition": "PNRM",
        "other_condition": "CHNM", "risk_level": "RLMD",
        "case_date": "2019-10-14",
        "perpetrators": [{"relationship": "RCPT", "first_name": "James",
                          "surname": "Kamau", "sex": "SMAL"}],
        "caregivers": [{"relationship": "CGPM", "first_name": "Mama",
                        "surname": "Atieno", "sex": "SMAL"}],
        "case_details": [{'category': 'CIDS',
                          'place_of_event': 'PEHF',
                          'date_of_event': '2019-09-01',
                          'nature_of_event': 'OOEV'}]}

data2 = {'hh_economic_status': 'UINC', 'child_sex': 'SFEM', 'case_reporter': 'CRSF',
        'physical_condition': 'no', 'case_date': '2020-09-13',
        'reporter_first_name': 'Leonard', 'county': '047', 'reporter_county': '047',
        'reporter_surname': 'mbugua',
        'perpetrators': [{'first_name': '', 'surname': '', 'relationship': '', 'sex': 'SMAL'}],
        'other_condition': 'CHNM', 'risk_level': 'RLMD', 'perpetrator': 'PKNW',
        'mental_condition': 'MNRM', 'family_status': 'FSUK', 'case_narration': "Leonard mbugua from nairobi county, kasarani sb county in ruai ward called the line with number 704241274 to say her neighbour  Tabitha Nyokabi age 17 years has been physically assaulted by her step father Antony wanjohi. her mothers name is Leah wangui. she says sometimes he makes sexual advances towards her. she has tried telling her mother about the incident and all she does is talk to him but does not chase him out of their home. she says she had reported the matter to the police station he was arrested and released on the same day. she was asking for assistance and she was referred to the chiefs office and the children's office", 'organization_unit': 'Helpline', 'caregivers': [
            {'first_name': 'Leah', 'surname': 'wangui', 'relationship': 'CGPM', 'sex': 'SMAL'}], 'reporter_sub_county': '280', 'case_details': [{'category': 'CSNG', 'place_of_event': 'PEHF', 'date_of_event': '2020-09-13', 'nature_of_event': 'OOEV'}], 'child_surname': 'wangui', 'reporter_telephone': '704241274', 'case_category': 'CSNG', 'case_landmark': 'st john primary', 'child_first_name': 'Leah', 'constituency': '280', 'child_dob': '2020-09-13'}

response = requests.post(url, json=data, headers=headers)
# data = {"case_id": "64d2a692-ef3c-11e9-98c6-d4258b5a3abb"}
# response = requests.get(url, params=data, headers=headers)

# print (response)
print('==' * 50, 'HEADERS', '==' * 50)
print(response.headers)
print('\n')
print('==' * 50, 'CONTENT', '==' * 50)
print(response.content)

'''
case_id = 'f6e09348-c5d2-11e9-9018-d4258b5a3abb'
response = requests.get(url, params={"case_id": case_id}, headers=headers)

print (response)
print (response.headers)
print (response.content)
'''
