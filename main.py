from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker
from models import Base, User, Task


DATABASE_URL = "sqlite:///./tasks.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
SECRET_KEY = "СУПЕР-ДУПЕР-СЕКРЕТНЫЙ-КЛЮЧ-ЙОУ-ПУМ-ПАМ-ПАМ"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(lifespan=lifespan)

def get_db():
    db = SessionLocal()
    yield db
    db.close()

def create_access_token(data, expires_delta=None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token=Depends(oauth2_scheme), db=Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except:
        raise HTTPException(status_code=401, detail="Неверный токен")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user

@app.get("/")
def root():
    return {"message": "Всё работает"}

@app.post("/register")
def register(data=Body(...), db=Depends(get_db)):
    user = User(
        username=data["username"],
        password=data["password"]
    )
    db.add(user)
    db.commit()

    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/login")
def login(form_data=Depends(OAuth2PasswordRequestForm), db=Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or user.password != form_data.password:
        raise HTTPException(status_code=401, detail="Неправильный логин или пароль")

    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/tasks")
def create_task(data=Body(...), db=Depends(get_db), current_user=Depends(get_current_user)):
    task = Task(
        title=data["title"],
        description=data.get("description", ""),
        status=data.get("status", "в ожидании"),
        priority=data.get("priority", 1),
        created_at=datetime.utcnow(),
        owner_id=current_user.id
    )
    db.add(task)
    db.commit()
    return task

@app.get("/tasks")
def get_tasks(search="", sort_by="created_at", db=Depends(get_db), current_user=Depends(get_current_user)):
    query = db.query(Task).filter(Task.owner_id == current_user.id)
    if search:
        query = query.filter(or_(Task.title.contains(search), Task.description.contains(search)))
    if sort_by == "title":
        query = query.order_by(Task.title)
    elif sort_by == "status":
        query = query.order_by(Task.status)
    else:
        query = query.order_by(Task.created_at)
    return query.all()

@app.get("/tasks/top/{n}")
def get_top_tasks(n, db=Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(Task).filter(Task.owner_id == current_user.id).order_by(Task.priority.desc()).limit(n).all()

@app.get("/tasks/{task_id}")
def get_task(task_id, db=Depends(get_db), current_user=Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task

@app.put("/tasks/{task_id}")
def update_task(task_id, data=Body(...), db=Depends(get_db), current_user=Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if "title" in data:
        task.title = data["title"]
    if "description" in data:
        task.description = data["description"]
    if "status" in data:
        task.status = data["status"]
    if "priority" in data:
        task.priority = data["priority"]
    db.commit()
    return task

@app.delete("/tasks/{task_id}")
def delete_task(task_id, db=Depends(get_db), current_user=Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    db.delete(task)
    db.commit()
    return {"message": "Удалено"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)