from .db import db
from datetime import datetime

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False, index=True)
    username = db.Column(db.String(64))
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    role = db.Column(db.String(16), default="client")  # admin, manager, client
    phone = db.Column(db.String(32))
    email = db.Column(db.String(120))
    delivery_address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)

class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), index=True)
    name = db.Column(db.String(255), nullable=False)
    sku = db.Column(db.String(64), unique=True)
    unit = db.Column(db.String(16), default="шт")
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(12,2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True)
    images_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Service(db.Model):
    __tablename__ = "services"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    base_price = db.Column(db.Numeric(12,2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True)

class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    status = db.Column(db.String(16), default="new")
    total = db.Column(db.Numeric(12,2), default=0)
    delivery_price = db.Column(db.Numeric(12,2), default=0)
    payment_status = db.Column(db.String(16), default="unpaid")
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), index=True)
    item_type = db.Column(db.String(16)) # product|service
    item_id = db.Column(db.Integer)
    qty = db.Column(db.Numeric(12,3), default=1)
    unit_price = db.Column(db.Numeric(12,2), default=0)
    total = db.Column(db.Numeric(12,2), default=0)

class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    target_type = db.Column(db.String(16))
    target_id = db.Column(db.Integer)
    rating = db.Column(db.Integer)
    text = db.Column(db.Text)
    is_moderated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Feedback(db.Model):
    __tablename__ = "feedback"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    name = db.Column(db.String(128))
    phone = db.Column(db.String(32))
    email = db.Column(db.String(120))
    subject = db.Column(db.String(255))
    message = db.Column(db.Text)
    status = db.Column(db.String(16), default="new")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
