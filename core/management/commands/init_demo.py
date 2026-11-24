from datetime import date, time, timedelta
from django.core.management.base import BaseCommand
from django.db import connection
from core.models import (
    Role, Group, Student, Instructor, User,
    Lesson, Enrollment, EnrollmentHistory, EnrollmentComment
)


class Command(BaseCommand):
    help = 'Создаёт SQL VIEW для отчёта и наполняет БД тестовыми данными автошколы'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("DROP VIEW IF EXISTS v_attendance_report;")
            cursor.execute("""
                CREATE VIEW v_attendance_report AS
                SELECT
                    l.lesson_date AS lesson_date,
                    g.number AS group_number,
                    i.full_name AS instructor_name,
                    COUNT(DISTINCT l.id) AS total_lessons,
                    SUM(CASE WHEN e.status = 'Проведена' THEN 1 ELSE 0 END) AS attended_count,
                    SUM(CASE WHEN e.status = 'Неявка' THEN 1 ELSE 0 END) AS no_show_count
                FROM lessons l
                JOIN groups g ON l.group_id = g.id
                JOIN instructors i ON l.instructor_id = i.id
                LEFT JOIN enrollments e ON e.lesson_id = l.id
                GROUP BY l.lesson_date, g.number, i.full_name;
            """)
        self.stdout.write(self.style.SUCCESS('SQL VIEW v_attendance_report создано.'))

        if User.objects.exists():
            self.stdout.write('Тестовые данные уже загружены.')
            return

        r_admin = Role.objects.create(name='Администратор', description='Полный доступ ко всем разделам')
        r_instr = Role.objects.create(name='Инструктор', description='Проведение занятий и отметка посещаемости')
        r_stud = Role.objects.create(name='Ученик', description='Запись на занятия и просмотр расписания')

        today = date.today()
        g101 = Group.objects.create(
            number='101', program='Категория B (МКПП)',
            start_date=today - timedelta(days=30), end_date=today + timedelta(days=60), status='Обучение'
        )
        g102 = Group.objects.create(
            number='102', program='Категория B (АКПП)',
            start_date=today - timedelta(days=15), end_date=today + timedelta(days=75), status='Обучение'
        )

        i1 = Instructor.objects.create(full_name='Иванов Иван Иванович', specialization='Категория B (МКПП)', car='Lada Vesta (А123ВС 39)')
        i2 = Instructor.objects.create(full_name='Сидоров Алексей Петрович', specialization='Категория B (АКПП)', car='Hyundai Solaris (К456МН 39)')

        s1 = Student.objects.create(full_name='Петров Пётр Сергеевич', phone='+7 (900) 111-22-33', group=g101, status='Активен')
        s2 = Student.objects.create(full_name='Смирнов Дмитрий Олегович', phone='+7 (900) 222-33-44', group=g101, status='Активен')
        s3 = Student.objects.create(full_name='Козлова Анна Викторовна', phone='+7 (900) 333-44-55', group=g102, status='Активен')
        s4 = Student.objects.create(full_name='Морозов Илья Андреевич', phone='+7 (900) 444-55-66', group=g102, status='Активен')

        u_admin = User(username='admin', role=r_admin, is_staff=True, is_superuser=True)
        u_admin.set_password('admin123')
        u_admin.save()

        u_ivanov = User(username='ivanov', role=r_instr, instructor=i1)
        u_ivanov.set_password('ivanov123')
        u_ivanov.save()

        u_sidorov = User(username='sidorov', role=r_instr, instructor=i2)
        u_sidorov.set_password('sidorov123')
        u_sidorov.save()

        u_petrov = User(username='petrov', role=r_stud, student=s1)
        u_petrov.set_password('petrov123')
        u_petrov.save()

        u_smirnov = User(username='smirnov', role=r_stud, student=s2)
        u_smirnov.set_password('smirnov123')
        u_smirnov.save()

        lessons = [
            Lesson.objects.create(lesson_date=today - timedelta(days=5), lesson_time=time(10, 0), type='Теория', instructor=i1, group=g101, place='Класс ПДД №1'),
            Lesson.objects.create(lesson_date=today - timedelta(days=4), lesson_time=time(12, 0), type='Практика', instructor=i1, group=g101, place='Автодром'),
            Lesson.objects.create(lesson_date=today - timedelta(days=3), lesson_time=time(14, 0), type='Практика', instructor=i2, group=g102, place='Город, маршрут №2'),
            Lesson.objects.create(lesson_date=today - timedelta(days=2), lesson_time=time(16, 0), type='Теория', instructor=i2, group=g102, place='Класс ПДД №2'),
            Lesson.objects.create(lesson_date=today, lesson_time=time(23, 30), type='Практика', instructor=i1, group=g101, place='Автодром'),
            Lesson.objects.create(lesson_date=today + timedelta(days=2), lesson_time=time(10, 0), type='Практика', instructor=i1, group=g101, place='Город, маршрут №1'),
            Lesson.objects.create(lesson_date=today + timedelta(days=3), lesson_time=time(11, 30), type='Практика', instructor=i2, group=g102, place='Автодром'),
            Lesson.objects.create(lesson_date=today + timedelta(days=4), lesson_time=time(15, 0), type='Теория', instructor=i1, group=g101, place='Класс ПДД №1'),
        ]

        demo_enrollments = [
            (s1, lessons[0], 'Проведена', 'Отработаны билеты 1–10', u_ivanov),
            (s2, lessons[0], 'Проведена', 'Присутствовал', u_ivanov),
            (s1, lessons[1], 'Проведена', 'Уверенная парковка задним ходом', u_ivanov),
            (s2, lessons[1], 'Неявка', 'Не предупредил об отсутствии', u_ivanov),
            (s3, lessons[2], 'Проведена', 'Хорошее управление на перекрёстках', u_sidorov),
            (s4, lessons[2], 'Проведена', 'Зачёт по змейке', u_sidorov),
            (s3, lessons[3], 'Неявка', 'Болезнь', u_sidorov),
            (s4, lessons[3], 'Проведена', 'Теория сдана', u_sidorov),
            (s1, lessons[4], 'Создана', 'Занятие сегодня (< 24 ч до начала)', u_petrov),
            (s2, lessons[4], 'Отменена', 'Отменено заранее', u_admin),
            (s1, lessons[5], 'Создана', 'Хочу отработать разворот', u_petrov),
            (s2, lessons[5], 'Подтверждена', 'Подтверждено инструктором', u_ivanov),
            (s3, lessons[6], 'Создана', 'Ожидает подтверждения', u_admin),
            (s4, lessons[6], 'Подтверждена', 'Подтверждено', u_sidorov),
            (s1, lessons[7], 'Создана', 'Запись на теорию', u_petrov),
        ]

        for st, les, status, note, actor in demo_enrollments:
            enr = Enrollment.objects.create(student=st, lesson=les, status=status, comment=note)
            EnrollmentHistory.objects.create(enrollment=enr, old_status='', new_status='Создана', changed_by=u_admin)
            if status != 'Создана':
                EnrollmentHistory.objects.create(enrollment=enr, old_status='Создана', new_status=status, changed_by=actor)
            if note:
                EnrollmentComment.objects.create(enrollment=enr, author=actor, text=note)

        self.stdout.write(self.style.SUCCESS('Демо-данные успешно загружены (5 пользователей, 15 записей)!'))
