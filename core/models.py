from django.db import models
from django.contrib.auth.models import AbstractUser


class Role(models.Model):
    name = models.CharField('Название', max_length=50, unique=True)
    description = models.CharField('Описание', max_length=255, blank=True)

    class Meta:
        db_table = 'roles'
        verbose_name = 'Роль'
        verbose_name_plural = 'Роли'

    def __str__(self):
        return self.name


class Group(models.Model):
    STATUS_CHOICES = [
        ('Набор', 'Набор'),
        ('Обучение', 'Обучение'),
        ('Выпуск', 'Выпуск'),
    ]
    number = models.CharField('Номер группы', max_length=20, unique=True)
    program = models.CharField('Программа обучения', max_length=100)
    start_date = models.DateField('Дата начала')
    end_date = models.DateField('Дата окончания')
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='Обучение')

    class Meta:
        db_table = 'groups'
        verbose_name = 'Группа'
        verbose_name_plural = 'Группы'

    def __str__(self):
        return f"Группа №{self.number} ({self.program})"


class Student(models.Model):
    STATUS_CHOICES = [
        ('Активен', 'Активен'),
        ('Академ', 'Академ'),
        ('Отчислен', 'Отчислен'),
        ('Выпущен', 'Выпущен'),
    ]
    full_name = models.CharField('ФИО', max_length=150)
    phone = models.CharField('Телефон', max_length=20)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='students', verbose_name='Группа')
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='Активен')

    class Meta:
        db_table = 'students'
        verbose_name = 'Ученик'
        verbose_name_plural = 'Ученики'

    def __str__(self):
        return f"{self.full_name} (гр. {self.group.number})"


class Instructor(models.Model):
    full_name = models.CharField('ФИО', max_length=150)
    specialization = models.CharField('Специализация', max_length=100)
    car = models.CharField('Автомобиль', max_length=100, blank=True)

    class Meta:
        db_table = 'instructors'
        verbose_name = 'Инструктор'
        verbose_name_plural = 'Инструкторы'

    def __str__(self):
        return f"{self.full_name} ({self.specialization})"


class User(AbstractUser):
    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True, verbose_name='Роль')
    student = models.OneToOneField(Student, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Ученик')
    instructor = models.OneToOneField(Instructor, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Инструктор')

    class Meta:
        db_table = 'users'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    @property
    def role_name(self):
        if self.is_superuser and not self.role:
            return 'Администратор'
        return self.role.name if self.role else 'Без роли'

    def display_name(self):
        if self.student:
            return self.student.full_name
        if self.instructor:
            return self.instructor.full_name
        return self.username


class Lesson(models.Model):
    TYPE_CHOICES = [
        ('Теория', 'Теория'),
        ('Практика', 'Практика'),
    ]
    lesson_date = models.DateField('Дата занятия', db_index=True)
    lesson_time = models.TimeField('Время занятия')
    type = models.CharField('Тип занятия', max_length=20, choices=TYPE_CHOICES)
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='lessons', verbose_name='Инструктор')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='lessons', verbose_name='Группа')
    place = models.CharField('Место проведения', max_length=150)

    class Meta:
        db_table = 'lessons'
        verbose_name = 'Занятие'
        verbose_name_plural = 'Занятия'
        indexes = [
            models.Index(fields=['lesson_date', 'instructor'], name='idx_lesson_date_instr'),
        ]

    def __str__(self):
        return f"{self.lesson_date.strftime('%d.%m.%Y')} {self.lesson_time.strftime('%H:%M')} ({self.type}, {self.instructor.full_name})"


class Enrollment(models.Model):
    STATUS_CREATED = 'Создана'
    STATUS_CONFIRMED = 'Подтверждена'
    STATUS_COMPLETED = 'Проведена'
    STATUS_CANCELLED = 'Отменена'
    STATUS_NO_SHOW = 'Неявка'

    STATUS_CHOICES = [
        (STATUS_CREATED, 'Создана'),
        (STATUS_CONFIRMED, 'Подтверждена'),
        (STATUS_COMPLETED, 'Проведена'),
        (STATUS_CANCELLED, 'Отменена'),
        (STATUS_NO_SHOW, 'Неявка'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments', verbose_name='Ученик')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='enrollments', verbose_name='Занятие')
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_CREATED, db_index=True)
    comment = models.TextField('Примечание', blank=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        db_table = 'enrollments'
        verbose_name = 'Запись на занятие'
        verbose_name_plural = 'Записи на занятия'
        unique_together = ('student', 'lesson')
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_enroll_status_date'),
        ]

    def __str__(self):
        return f"Запись №{self.id}: {self.student.full_name} -> {self.lesson}"


class EnrollmentHistory(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='history', verbose_name='Запись')
    old_status = models.CharField('Прежний статус', max_length=20, blank=True)
    new_status = models.CharField('Новый статус', max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Кем изменено')
    changed_at = models.DateTimeField('Время изменения', auto_now_add=True)

    class Meta:
        db_table = 'enrollment_history'
        ordering = ['changed_at']


class EnrollmentComment(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='comments', verbose_name='Запись')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Автор')
    text = models.TextField('Текст комментария')
    created_at = models.DateTimeField('Время добавления', auto_now_add=True)

    class Meta:
        db_table = 'enrollment_comments'
        ordering = ['created_at']
