import csv
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import connection, IntegrityError
from django.http import HttpResponse
import openpyxl

from .models import (
    Role, Group, Student, Instructor, User,
    Lesson, Enrollment, EnrollmentHistory, EnrollmentComment
)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('enrollment_list')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('enrollment_list')
        messages.error(request, 'Неверный логин или пароль.')
    return render(request, 'core/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def enrollment_list(request):
    user = request.user
    role = user.role_name

    qs = Enrollment.objects.select_related(
        'student', 'student__group', 'lesson', 'lesson__instructor', 'lesson__group'
    ).order_by('-lesson__lesson_date', '-lesson__lesson_time')

    if role == 'Инструктор' and user.instructor:
        qs = qs.filter(lesson__instructor=user.instructor)
    elif role == 'Ученик' and user.student:
        qs = qs.filter(student=user.student)
    elif role != 'Администратор':
        qs = qs.none()

    status_filter = request.GET.get('status', '')
    instructor_filter = request.GET.get('instructor', '')
    date_filter = request.GET.get('date', '')

    if status_filter:
        qs = qs.filter(status=status_filter)
    if instructor_filter:
        qs = qs.filter(lesson__instructor_id=instructor_filter)
    if date_filter:
        qs = qs.filter(lesson__lesson_date=date_filter)

    instructors = Instructor.objects.all()
    return render(request, 'core/enrollment_list.html', {
        'enrollments': qs,
        'instructors': instructors,
        'statuses': Enrollment.STATUS_CHOICES,
        'status_filter': status_filter,
        'instructor_filter': instructor_filter,
        'date_filter': date_filter,
    })


@login_required
def enrollment_create(request):
    user = request.user
    role = user.role_name

    if role not in ('Администратор', 'Ученик'):
        messages.error(request, 'У вашей роли нет прав на создание записи.')
        return redirect('enrollment_list')

    if role == 'Ученик':
        if not user.student:
            messages.error(request, 'Профиль ученика не привязан к учётной записи.')
            return redirect('enrollment_list')
        students = Student.objects.filter(id=user.student.id)
        lessons = Lesson.objects.filter(group=user.student.group).select_related('instructor', 'group').order_by('lesson_date', 'lesson_time')
    else:
        students = Student.objects.select_related('group').all()
        lessons = Lesson.objects.select_related('instructor', 'group').order_by('lesson_date', 'lesson_time')

    preselected_lesson = request.GET.get('lesson_id', '')

    if request.method == 'POST':
        student_id = user.student.id if role == 'Ученик' else request.POST.get('student_id')
        lesson_id = request.POST.get('lesson_id')
        comment = request.POST.get('comment', '').strip()

        student = get_object_or_404(Student, id=student_id)
        lesson = get_object_or_404(Lesson, id=lesson_id)

        if student.group_id != lesson.group_id:
            messages.error(request, 'Ошибка: ученик может записаться только на занятие своей группы!')
            return redirect('enrollment_create')

        try:
            enrollment = Enrollment.objects.create(
                student=student,
                lesson=lesson,
                status=Enrollment.STATUS_CREATED,
                comment=comment
            )
            EnrollmentHistory.objects.create(
                enrollment=enrollment,
                old_status='',
                new_status=Enrollment.STATUS_CREATED,
                changed_by=user
            )
            if comment:
                EnrollmentComment.objects.create(
                    enrollment=enrollment,
                    author=user,
                    text=comment
                )
            messages.success(request, f'Запись №{enrollment.id} успешно создана.')
            return redirect('enrollment_detail', pk=enrollment.id)
        except IntegrityError:
            messages.error(request, 'Этот ученик уже записан на данное занятие.')

    return render(request, 'core/enrollment_form.html', {
        'students': students,
        'lessons': lessons,
        'preselected_lesson': preselected_lesson,
    })


@login_required
def enrollment_detail(request, pk):
    enrollment = get_object_or_404(
        Enrollment.objects.select_related('student', 'student__group', 'lesson', 'lesson__instructor', 'lesson__group'),
        pk=pk
    )
    user = request.user
    role = user.role_name

    if role == 'Ученик' and enrollment.student != user.student:
        messages.error(request, 'Доступ запрещён: вы можете просматривать только свои записи.')
        return redirect('enrollment_list')
    if role == 'Инструктор' and enrollment.lesson.instructor != user.instructor:
        messages.error(request, 'Доступ запрещён: это занятие другого инструктора.')
        return redirect('enrollment_list')

    allowed_actions = []
    lesson_dt = datetime.combine(enrollment.lesson.lesson_date, enrollment.lesson.lesson_time)
    hours_left = (lesson_dt - datetime.now()).total_seconds() / 3600

    if enrollment.status == Enrollment.STATUS_CREATED:
        if role in ('Администратор', 'Инструктор'):
            allowed_actions.append(('Подтверждена', 'Подтвердить запись', 'btn-success'))
        if role == 'Администратор':
            allowed_actions.append(('Отменена', 'Отменить запись', 'btn-danger'))
        elif role == 'Ученик' and hours_left >= 24:
            allowed_actions.append(('Отменена', 'Отменить запись (более 24 ч)', 'btn-danger'))

    elif enrollment.status == Enrollment.STATUS_CONFIRMED:
        if role in ('Администратор', 'Инструктор'):
            allowed_actions.append(('Проведена', 'Отметить: Проведена', 'btn-primary'))
            allowed_actions.append(('Неявка', 'Отметить: Неявка', 'btn-warning'))
        if role == 'Администратор':
            allowed_actions.append(('Отменена', 'Отменить запись', 'btn-danger'))

    return render(request, 'core/enrollment_detail.html', {
        'enrollment': enrollment,
        'allowed_actions': allowed_actions,
        'hours_left': round(hours_left, 1),
    })


@login_required
def enrollment_change_status(request, pk):
    if request.method != 'POST':
        return redirect('enrollment_detail', pk=pk)

    enrollment = get_object_or_404(Enrollment, pk=pk)
    new_status = request.POST.get('new_status')
    user = request.user
    role = user.role_name
    old_status = enrollment.status

    lesson_dt = datetime.combine(enrollment.lesson.lesson_date, enrollment.lesson.lesson_time)
    hours_left = (lesson_dt - datetime.now()).total_seconds() / 3600

    valid = False
    if old_status == Enrollment.STATUS_CREATED:
        if new_status == Enrollment.STATUS_CONFIRMED and role in ('Администратор', 'Инструктор'):
            if role == 'Администратор' or enrollment.lesson.instructor == user.instructor:
                valid = True
        elif new_status == Enrollment.STATUS_CANCELLED:
            if role == 'Администратор':
                valid = True
            elif role == 'Ученик' and enrollment.student == user.student and hours_left >= 24:
                valid = True
    elif old_status == Enrollment.STATUS_CONFIRMED:
        if new_status in (Enrollment.STATUS_COMPLETED, Enrollment.STATUS_NO_SHOW) and role in ('Администратор', 'Инструктор'):
            if role == 'Администратор' or enrollment.lesson.instructor == user.instructor:
                valid = True
        elif new_status == Enrollment.STATUS_CANCELLED and role == 'Администратор':
            valid = True

    if not valid:
        messages.error(request, f'Недопустимый переход из «{old_status}» в «{new_status}» или недостаточно прав.')
        return redirect('enrollment_detail', pk=pk)

    enrollment.status = new_status
    enrollment.save()
    EnrollmentHistory.objects.create(
        enrollment=enrollment,
        old_status=old_status,
        new_status=new_status,
        changed_by=user
    )
    messages.success(request, f'Статус изменён на «{new_status}».')
    return redirect('enrollment_detail', pk=pk)


@login_required
def enrollment_add_comment(request, pk):
    if request.method == 'POST':
        enrollment = get_object_or_404(Enrollment, pk=pk)
        text = request.POST.get('text', '').strip()
        if text:
            EnrollmentComment.objects.create(
                enrollment=enrollment,
                author=request.user,
                text=text
            )
            messages.success(request, 'Комментарий добавлен.')
    return redirect('enrollment_detail', pk=pk)


@login_required
def enrollment_delete(request, pk):
    if request.user.role_name != 'Администратор':
        messages.error(request, 'Удаление записей доступно только администратору.')
        return redirect('enrollment_list')
    if request.method == 'POST':
        enrollment = get_object_or_404(Enrollment, pk=pk)
        enrollment.delete()
        messages.success(request, 'Запись удалена из базы данных.')
    return redirect('enrollment_list')


@login_required
def schedule_view(request):
    user = request.user
    role = user.role_name

    lessons = Lesson.objects.select_related('instructor', 'group').order_by('lesson_date', 'lesson_time')

    if role == 'Инструктор' and user.instructor:
        lessons = lessons.filter(instructor=user.instructor)
    elif role == 'Ученик' and user.student:
        lessons = lessons.filter(group=user.student.group)

    if request.method == 'POST' and role == 'Администратор':
        Lesson.objects.create(
            lesson_date=request.POST.get('lesson_date'),
            lesson_time=request.POST.get('lesson_time'),
            type=request.POST.get('type'),
            instructor_id=request.POST.get('instructor_id'),
            group_id=request.POST.get('group_id'),
            place=request.POST.get('place', 'Учебный класс №1')
        )
        messages.success(request, 'Занятие добавлено в расписание.')
        return redirect('schedule')

    return render(request, 'core/schedule.html', {
        'lessons': lessons,
        'instructors': Instructor.objects.all(),
        'groups': Group.objects.all(),
    })


@login_required
def directories_view(request):
    if request.user.role_name != 'Администратор':
        messages.error(request, 'Доступ только для администратора.')
        return redirect('enrollment_list')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_group':
            Group.objects.create(
                number=request.POST.get('number'),
                program=request.POST.get('program'),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date'),
                status='Обучение'
            )
            messages.success(request, 'Группа добавлена.')

        elif action == 'add_instructor':
            Instructor.objects.create(
                full_name=request.POST.get('full_name'),
                specialization=request.POST.get('specialization'),
                car=request.POST.get('car', '')
            )
            messages.success(request, 'Инструктор добавлен.')

        elif action == 'add_student':
            Student.objects.create(
                full_name=request.POST.get('full_name'),
                phone=request.POST.get('phone'),
                group_id=request.POST.get('group_id'),
                status='Активен'
            )
            messages.success(request, 'Ученик добавлен.')

        return redirect('directories')

    return render(request, 'core/directories.html', {
        'groups': Group.objects.all(),
        'instructors': Instructor.objects.all(),
        'students': Student.objects.select_related('group').all(),
    })


@login_required
def users_view(request):
    if request.user.role_name != 'Администратор':
        messages.error(request, 'Управление пользователями доступно только администратору.')
        return redirect('enrollment_list')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            login_val = request.POST.get('username').strip()
            password_val = request.POST.get('password')
            role_id = request.POST.get('role_id')
            student_id = request.POST.get('student_id') or None
            instructor_id = request.POST.get('instructor_id') or None

            if User.objects.filter(username=login_val).exists():
                messages.error(request, 'Пользователь с таким логином уже существует.')
            else:
                u = User(
                    username=login_val,
                    role_id=role_id,
                    student_id=student_id,
                    instructor_id=instructor_id,
                )
                u.set_password(password_val)
                u.save()
                messages.success(request, f'Пользователь {login_val} создан.')

        elif action == 'delete':
            uid = request.POST.get('user_id')
            if str(request.user.id) == str(uid):
                messages.error(request, 'Нельзя удалить самого себя.')
            else:
                User.objects.filter(id=uid).delete()
                messages.success(request, 'Пользователь удалён.')

        return redirect('users')

    return render(request, 'core/users.html', {
        'users': User.objects.select_related('role', 'student', 'instructor').all(),
        'roles': Role.objects.all(),
        'students': Student.objects.all(),
        'instructors': Instructor.objects.all(),
    })


def _get_report_rows(date_from, date_to):
    query = "SELECT group_number, instructor_name, total_lessons, attended_count, no_show_count FROM v_attendance_report WHERE 1=1"
    params = []

    if date_from:
        query += " AND lesson_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND lesson_date <= %s"
        params.append(date_to)

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        raw_rows = cursor.fetchall()

    summary = {}
    for g_num, instr_name, lessons_cnt, att_cnt, noshow_cnt in raw_rows:
        key = (g_num, instr_name)
        if key not in summary:
            summary[key] = {
                'group': g_num,
                'instructor': instr_name,
                'lessons': 0,
                'attended': 0,
                'no_show': 0,
            }
        summary[key]['lessons'] += lessons_cnt or 0
        summary[key]['attended'] += att_cnt or 0
        summary[key]['no_show'] += noshow_cnt or 0

    return list(summary.values())


@login_required
def report_view(request):
    if request.user.role_name != 'Администратор':
        messages.error(request, 'Отчёты доступны только администратору.')
        return redirect('enrollment_list')

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    rows = _get_report_rows(date_from, date_to)

    chart_labels = [f"Гр. {r['group']} ({r['instructor'].split()})" for r in rows]
    chart_attended = [r['attended'] for r in rows]
    chart_noshow = [r['no_show'] for r in rows]

    return render(request, 'core/report.html', {
        'rows': rows,
        'date_from': date_from,
        'date_to': date_to,
        'chart_labels': chart_labels,
        'chart_attended': chart_attended,
        'chart_noshow': chart_noshow,
    })


@login_required
def export_csv(request):
    if request.user.role_name != 'Администратор':
        return HttpResponse('Доступ запрещён', status=403)

    rows = _get_report_rows(request.GET.get('date_from', ''), request.GET.get('date_to', ''))

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Группа', 'Инструктор', 'Занятий', 'Посещено', 'Неявок'])
    for r in rows:
        writer.writerow([r['group'], r['instructor'], r['lessons'], r['attended'], r['no_show']])

    return response


@login_required
def export_excel(request):
    if request.user.role_name != 'Администратор':
        return HttpResponse('Доступ запрещён', status=403)

    rows = _get_report_rows(request.GET.get('date_from', ''), request.GET.get('date_to', ''))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Отчёт по посещаемости'
    ws.append(['Группа', 'Инструктор', 'Занятий', 'Посещено', 'Неявок'])
    for r in rows:
        ws.append([r['group'], r['instructor'], r['lessons'], r['attended'], r['no_show']])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.xlsx"'
    wb.save(response)

    return response