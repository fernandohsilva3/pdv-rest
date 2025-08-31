from fastapi import FastAPI, HTTPException, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, Session, relationship
from datetime import datetime
import os

DB_PATH = os.getenv("PDV_DB_PATH", "sqlite:///./pdv.db")

engine = create_engine(DB_PATH, connect_args={"check_same_thread": False} if DB_PATH.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    price = Column(Float, nullable=False)

class Table(Base):
    __tablename__ = "tables"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    total = Column(Float, nullable=False)
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    subtotal = Column(Float, nullable=False)
    order = relationship("Order", back_populates="items")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="PDV Restaurante - API (com Mesas e Relatórios)")
templates = Jinja2Templates(directory="templates")

# CORS - permita Android na rede local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- Pydantic Schemas ----------------
class ProductIn(BaseModel):
    name: str
    price: float

class ProductOut(BaseModel):
    id: int
    name: str
    price: float
    class Config:
        from_attributes = True

class TableIn(BaseModel):
    name: str

class TableOut(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True

class OrderItemIn(BaseModel):
    product_id: int
    quantity: int

class OrderRequest(BaseModel):
    table_id: Optional[int] = None
    items: List[OrderItemIn]

class OrderItemOut(BaseModel):
    product_id: int
    name: str
    unit_price: float
    quantity: int
    subtotal: float

class OrderResponse(BaseModel):
    id: int
    table_id: Optional[int]
    items: List[OrderItemOut]
    total: float
    created_at: datetime

# ---------------- API Endpoints ----------------
@app.get("/products", response_model=List[ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).order_by(Product.name.asc()).all()

@app.post("/products", response_model=ProductOut)
def create_product(payload: ProductIn, db: Session = Depends(get_db)):
    exists = db.query(Product).filter(Product.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=400, detail="Produto já existe")
    p = Product(name=payload.name, price=payload.price)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

@app.put("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: int, payload: ProductIn, db: Session = Depends(get_db)):
    p = db.query(Product).get(product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    p.name = payload.name
    p.price = payload.price
    db.commit()
    db.refresh(p)
    return p

@app.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(Product).get(product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    db.delete(p)
    db.commit()
    return {"ok": True}

# --- Tables ---
@app.get("/tables", response_model=List[TableOut])
def list_tables(db: Session = Depends(get_db)):
    return db.query(Table).order_by(Table.name.asc()).all()

@app.post("/tables", response_model=TableOut)
def create_table(payload: TableIn, db: Session = Depends(get_db)):
    exists = db.query(Table).filter(Table.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=400, detail="Mesa já existe")
    t = Table(name=payload.name)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

# --- Orders: create and list (reports) ---
@app.post("/order", response_model=OrderResponse)
def make_order(order_req: OrderRequest, db: Session = Depends(get_db)):
    items_out = []
    total = 0.0
    # validate products and compute subtotal
    for it in order_req.items:
        prod = db.query(Product).get(it.product_id)
        if not prod:
            raise HTTPException(status_code=404, detail=f"Produto {it.product_id} não encontrado")
        subtotal = round(prod.price * it.quantity, 2)
        total += subtotal
        items_out.append((prod, it.quantity, subtotal))
    total = round(total, 2)
    # create order record
    ord = Order(table_id=order_req.table_id, total=total)
    db.add(ord)
    db.commit()
    db.refresh(ord)
    # create items
    for prod, qty, subtotal in items_out:
        oi = OrderItem(order_id=ord.id, product_id=prod.id, quantity=qty, subtotal=subtotal)
        db.add(oi)
    db.commit()
    # prepare response
    resp_items = []
    for oi in ord.items:
        prod = db.query(Product).get(oi.product_id)
        resp_items.append(OrderItemOut(
            product_id=prod.id,
            name=prod.name,
            unit_price=prod.price,
            quantity=oi.quantity,
            subtotal=oi.subtotal
        ))
    return OrderResponse(id=ord.id, table_id=ord.table_id, items=resp_items, total=ord.total, created_at=ord.created_at)

@app.get("/orders")
def list_orders(from_date: Optional[str] = Query(None), to_date: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(Order)
    if from_date:
        try:
            f = datetime.fromisoformat(from_date)
            query = query.filter(Order.created_at >= f)
        except:
            raise HTTPException(status_code=400, detail="from_date inválida, use YYYY-MM-DD or ISO format")
    if to_date:
        try:
            t = datetime.fromisoformat(to_date)
            query = query.filter(Order.created_at <= t)
        except:
            raise HTTPException(status_code=400, detail="to_date inválida, use YYYY-MM-DD or ISO format")
    orders = query.order_by(Order.created_at.desc()).all()
    # build simple JSON report
    result = []
    total_sum = 0.0
    for o in orders:
        items = []
        for it in o.items:
            p = db.query(Product).get(it.product_id)
            items.append({"product_id": p.id, "name": p.name, "quantity": it.quantity, "subtotal": it.subtotal})
        result.append({"id": o.id, "table_id": o.table_id, "created_at": o.created_at.isoformat(), "total": o.total, "items": items})
        total_sum += o.total
    return {"orders": result, "total_sum": round(total_sum,2)}

# ---------------- Backoffice simple (HTML) ----------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.name.asc()).all()
    tables = db.query(Table).order_by(Table.name.asc()).all()
    return templates.TemplateResponse("products.html", {"request": request, "products": products, "tables": tables})

@app.get("/admin/new", response_class=HTMLResponse)
def new_form(request: Request):
    return templates.TemplateResponse("product_form.html", {"request": request, "action": "/admin/new", "name": "", "price": ""})

@app.post("/admin/new", response_class=HTMLResponse)
def create_from_form(request: Request, name: str = Form(...), price: float = Form(...), db: Session = Depends(get_db)):
    p = Product(name=name, price=price)
    db.add(p)
    db.commit()
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/" />')

@app.get("/admin/edit/{product_id}", response_class=HTMLResponse)
def edit_form(product_id: int, request: Request, db: Session = Depends(get_db)):
    p = db.query(Product).get(product_id)
    if not p:
        return HTMLResponse("Produto não encontrado", status_code=404)
    return templates.TemplateResponse("product_form.html", {"request": request, "action": f"/admin/edit/{p.id}", "name": p.name, "price": p.price})

@app.post("/admin/edit/{product_id}", response_class=HTMLResponse)
def edit_from_form(product_id: int, request: Request, name: str = Form(...), price: float = Form(...), db: Session = Depends(get_db)):
    p = db.query(Product).get(product_id)
    if not p:
        return HTMLResponse("Produto não encontrado", status_code=404)
    p.name = name
    p.price = price
    db.commit()
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/" />')

@app.get("/admin/delete/{product_id}", response_class=HTMLResponse)
def delete_from_list(product_id: int, db: Session = Depends(get_db)):
    p = db.query(Product).get(product_id)
    if p:
        db.delete(p)
        db.commit()
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/" />')

# --- Tables admin ---
@app.get("/admin/tables", response_class=HTMLResponse)
def tables_list(request: Request, db: Session = Depends(get_db)):
    tables = db.query(Table).order_by(Table.name.asc()).all()
    return templates.TemplateResponse("tables.html", {"request": request, "tables": tables})

@app.post("/admin/tables/new", response_class=HTMLResponse)
def tables_create(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    t = Table(name=name)
    db.add(t)
    db.commit()
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/admin/tables" />')

# --- Reports page ---
@app.get("/admin/reports", response_class=HTMLResponse)
def reports_page(request: Request, db: Session = Depends(get_db), from_date: Optional[str] = None, to_date: Optional[str] = None):
    query = db.query(Order)
    if from_date:
        try:
            f = datetime.fromisoformat(from_date)
            query = query.filter(Order.created_at >= f)
        except:
            pass
    if to_date:
        try:
            t = datetime.fromisoformat(to_date)
            query = query.filter(Order.created_at <= t)
        except:
            pass
    orders = query.order_by(Order.created_at.desc()).all()
    total_sum = sum(o.total for o in orders)
    return templates.TemplateResponse("reports.html", {"request": request, "orders": orders, "total_sum": round(total_sum,2), "from_date": from_date or "", "to_date": to_date or ""})