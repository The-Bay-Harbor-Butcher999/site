from django.contrib import admin
from .models import Role, Group, Student, Instructor, User, Lesson, Enrollment

admin.site.register([Role, Group, Student, Instructor, User, Lesson, Enrollment])
