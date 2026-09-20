from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-me-in-production')

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'sqlite:///starsport.db'
).replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100))
    expiry = db.Column(db.Date)
    package = db.Column(db.String(50), default='شهري')

    def to_dict(self):
        days = (self.expiry - datetime.now().date()).days if self.expiry else 0
        return {
            'phone': self.phone,
            'name': self.name,
            'expiry': self.expiry.strftime('%Y-%m-%d') if self.expiry else '-',
            'package': self.package,
            'days_left': days,
            'status': 'active' if days > 0 else 'expired'
        }


class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='viewer')


class RenewalRequest(db.Model):
    __tablename__ = 'renewal_requests'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20))
    name = db.Column(db.String(100))
    months = db.Column(db.Integer)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    handled_by = db.Column(db.String(50))

    def to_dict(self):
        return {
            'id': self.id,
            'phone': self.phone,
            'name': self.name,
            'months': self.months,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'handled_by': self.handled_by
        }


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/check', methods=['POST'])
def check_user():
    data = request.get_json() or {}
    phone = data.get('phone', '').strip()
    if not phone:
        return jsonify({'ok': False, 'msg': 'ادخل الرقم'}), 400
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify({'ok': False, 'msg': 'الرقم ده مش مسجل'}), 404
    return jsonify({'ok': True, 'user': user.to_dict()})


@app.route('/api/renew', methods=['POST'])
def renew_request():
    data = request.get_json() or {}
    phone = data.get('phone')
    months = int(data.get('months', 1))

    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify({'ok': False, 'msg': 'المشترك غير موجود'}), 404

    existing = RenewalRequest.query.filter_by(phone=phone, status='pending').first()
    if existing:
        return jsonify({'ok': False, 'msg': 'فيه طلب معلق بالفعل'}), 400

    req = RenewalRequest(phone=phone, name=user.name, months=months)
    db.session.add(req)
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم إرسال الطلب'})


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        admin = Admin.query.filter_by(username=u).first()
        if admin and check_password_hash(admin.password_hash, p):
            session['admin_id'] = admin.id
            session['admin_name'] = admin.name
            session['admin_role'] = admin.role
            return redirect(url_for('admin_panel'))
        return render_template('admin_login.html', error='بيانات غلط')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/admin')
def admin_panel():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    return render_template('admin.html',
                           admin_name=session['admin_name'],
                           admin_role=session['admin_role'])


@app.route('/api/admin/requests')
def admin_requests():
    if 'admin_id' not in session:
        return jsonify({'ok': False}), 401
    reqs = RenewalRequest.query.order_by(RenewalRequest.created_at.desc()).all()
    return jsonify([r.to_dict() for r in reqs])


@app.route('/api/admin/handle', methods=['POST'])
def handle_request():
    if 'admin_id' not in session:
        return jsonify({'ok': False, 'msg': 'لازم تسجل دخول'}), 401
    if session.get('admin_role') != 'super_admin':
        return jsonify({'ok': False, 'msg': 'مش عندك صلاحية'}), 403

    data = request.get_json() or {}
    req_id = data.get('id')
    action = data.get('action')

    req = RenewalRequest.query.get(req_id)
    if not req:
        return jsonify({'ok': False, 'msg': 'الطلب غير موجود'}), 404

    if action == 'approve':
        user = User.query.filter_by(phone=req.phone).first()
        if user:
            base = user.expiry if user.expiry and user.expiry > datetime.now().date() else datetime.now().date()
            user.expiry = base + timedelta(days=30 * req.months)
        req.status = 'approved'
    else:
        req.status = 'rejected'

    req.handled_by = session['admin_name']
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/users')
def admin_users():
    if 'admin_id' not in session:
        return jsonify({'ok': False}), 401
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])


@app.before_request
def init_data():
    if not getattr(app, '_initialized', False):
        db.create_all()
        if not Admin.query.first():
            db.session.add(Admin(
                username='admin',
                password_hash=generate_password_hash('Star@2026'),
                name='المدير العام',
                role='super_admin'
            ))
            db.session.add(Admin(
                username='employee1',
                password_hash=generate_password_hash('Emp@2026'),
                name='الموظف أحمد',
                role='viewer'
            ))
        if not User.query.first():
            today = datetime.now().date()
            db.session.add(User(phone='01006654853', name='مشترك تجريبي',
                                expiry=today + timedelta(days=30), package='شهري'))
            db.session.add(User(phone='01111111111', name='أحمد',
                                expiry=today + timedelta(days=5), package='شهري'))
        db.session.commit()
        app._initialized = True


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
