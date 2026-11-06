"""Запуск: python -m uvicorn file:app --reload"""
import csv
import hashlib
import os
import secrets
from urllib.parse import quote, unquote

from fastapi import FastAPI, Form, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
app.mount('/sources', StaticFiles(directory='sources'), name='sources')
templates = Jinja2Templates(directory='templates')

white_urls = ['/', '/home', '/login', '/logout', '/register', '/main', '/404']

FILE = 'users.csv'


def read_users():
    if not os.path.exists(FILE):          
        return []
    with open(FILE, encoding='utf-8-sig', newline='') as f:  
        return list(csv.DictReader(f))


def make_hash(password, salt):
    #Превращает пароль в длинную строку, из которой пароль не вернуть
    return hashlib.sha256((salt + password).encode()).hexdigest()


def hash_password(password):
    #создаёт случайную соль из 16 символов
    salt = secrets.token_hex(8)
    return salt + '$' + make_hash(password, salt)


def check_password(password, saved):
    #Для входа: берём соль из файла, хэшируем введённый пароль и сравниваем
    salt = saved.split('$')[0]
    return saved == salt + '$' + make_hash(password, salt)


def find_user(email):
    #Найти пользователя по почте. Если не нашли — вернётся None.
    for user in read_users():
        if user['email'] == email:
            return user
    return None


def add_user(name, email, password):
    #Дописать нового пользователя в конец файла.
    new_file = not os.path.exists(FILE)
    with open(FILE, 'a', encoding='utf-8-sig', newline='') as f:   # 'a' — дописывать в конец
        writer = csv.writer(f)
        if new_file:
            writer.writerow(['name', 'email', 'password'])        
        writer.writerow([name, email, hash_password(password)])   


def current_name(request):
    #Имя пользователя из cookie
    return unquote(request.cookies.get('username', '')) or 'красотка'


# ===== Страницы =====
@app.get('/', response_class=HTMLResponse)
def main_page(request: Request):
    return templates.TemplateResponse(
        request=request, name='home.html', context={'username': current_name(request)})


@app.get('/home', response_class=HTMLResponse)
def home_page(request: Request):
    return templates.TemplateResponse(
        request=request, name='home.html', context={'username': current_name(request)})


@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request, registered: str = None):
    notice = None
    if registered:
        notice = 'Аккаунт создан! Теперь войди 💖'
    return templates.TemplateResponse(request=request, name='login.html', context={'notice': notice})


@app.get('/register', response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request=request, name='register.html')


@app.get('/main', response_class=HTMLResponse)
def cabinet_page(request: Request):
    return templates.TemplateResponse(
        request=request, name='main.html', context={'username': current_name(request)})


@app.get('/logout')
def logout():
    response = RedirectResponse(url='/login')
    response.delete_cookie('username')      # забываем, кто вошёл
    return response


@app.get('/404', response_class=HTMLResponse)
def oshibka_page(request: Request):
    return templates.TemplateResponse(request=request, name='404.html')


# Любой несуществующий адрес показывает страницу 404
@app.exception_handler(StarletteHTTPException)
async def not_found_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(request=request, name='404.html', status_code=404)
    return await http_exception_handler(request, exc)


@app.post('/register')
def register(request: Request,
            name: str = Form(...),
            email: str = Form(...),
            password: str = Form(...)):
    email = email.strip().lower()

    if find_user(email):                    
        return templates.TemplateResponse(
            request=request, name='register.html',
            context={'error': 'Такой email уже зарегистрирован'})

    add_user(name.strip(), email, password)
    print('Новый пользователь:', email)
    return RedirectResponse(url='/login?registered=1', status_code=303)


@app.post('/login')
def login(request: Request,
        username: str = Form(...),        
        password: str = Form(...)):
    user = find_user(username.strip().lower())

    if user is None or not check_password(password, user['password']):    # нет такого или пароль не тот
        return templates.TemplateResponse(
            request=request, name='login.html',
            context={'error': 'Неверный email или пароль'})

    print('Вошёл пользователь:', user['email'])    
    response = RedirectResponse(url='/main', status_code=303)
    response.set_cookie('username', quote(user['name']))
    return response