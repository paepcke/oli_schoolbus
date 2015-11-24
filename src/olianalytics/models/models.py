'''
Created on Nov 23, 2015

@author: paepcke
'''

class StudentPropertyEntity (object):
    '''
    Mockup of student entity. True code is in the real models.py.
    '''


    def __init__(self, params):
        '''
        Constructor
        '''
        self.students = {}
    
    def get(self, student, property_key):
        '''
        Given a student and a property name,
        return the requested property. If either
        the student or the property do not exist,
        returns None.
        
        :param student:
        :param property_key:
        '''
        try:
            self.students[student].get(property_key)
        except KeyError:
            # Student not found:
            return None
        
    def create(self, Student=None, Property_name=None):
        if Student is None or Property_name is None:
            raise ValueError('Need to provide both student and property name.')
        the_student = self.students.get(Student, None) 
        if the_student is None:
            the_student = Student()
        the_student[Property_name] = self
        return self
        
        
class Student(object):
    
    def __init__(self):
        self.properties = {}
        
    def get(self, key, default=None):
        '''
        Returns requested property of this student instance.
        Return None on failure to find property, unless default
        is provided.
        
        :param key: property name.
        :param default: what to return if property not defined for student.
        '''
        
        return self.properties.get(key, default)
    
    def setitem(self, key, value):
        self.properties[key] = value
    
    