from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = "starsport-2026"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///starsport.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
VODAFONE = "01006654853"


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20))
    card_number = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(100))
    expiry = db.Column(db.Date)
    last_amount = db.Column(db.Float, default=0)

    def to_dict(self):
        days = (self.expiry - datetime.now().date()).days if self.expiry else 0
        return {'id': self.id, 'phone': self.phone or '',
                'card_number': self.card_number, 'name': self.name or '',
                'last_amount': self.last_amount or 0,
                'expiry': self.expiry.strftime('%Y-%m-%d') if self.expiry else '-',
                'days_left': days, 'status': 'active' if days > 0 else 'expired'}


class Channel(db.Model):
    __tablename__ = 'channels'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.Float, default=0)
    problem = db.Column(db.Text, default='')

    def to_dict(self):
        return {'id': self.id, 'name': self.name or '',
                'price': self.price or 0, 'problem': self.problem or ''}


class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(100))


class RenewalRequest(db.Model):
    __tablename__ = 'renewals'
    id = db.Column(db.Integer, primary_key=True)
    card_number = db.Column(db.String(100))
    name = db.Column(db.String(100))
    months = db.Column(db.Integer)
    from_phone = db.Column(db.String(20))
    amount = db.Column(db.Float, default=0)
    screenshot = db.Column(db.String(255))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'card_number': self.card_number,
                'name': self.name, 'months': self.months,
                'from_phone': self.from_phone, 'amount': self.amount or 0,
                'screenshot': self.screenshot, 'status': self.status,
                'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else ''}


class ChannelIssue(db.Model):
    __tablename__ = 'issues'
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer)
    channel_name = db.Column(db.String(100))
    customer_name = db.Column(db.String(100))
    card_number = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'channel_id': self.channel_id,
                'channel_name': self.channel_name,
                'customer_name': self.customer_name,
                'card_number': self.card_number, 'phone': self.phone,
                'message': self.message,
                'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else ''}


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/renew')
def renew_page():
    return render_template('renew.html', vodafone=VODAFONE)


@app.route('/vodafone')
def vodafone_page():
    return render_template('vodafone.html', vodafone=VODAFONE)


@app.route('/remaining')
def remaining_page():
    return render_template('remaining.html')


@app.route('/channels')
def channels_page():
    return render_template('channels.html')


@app.route('/support')
def support_page():
    return render_template('support.html')


@app.route('/api/search', methods=['POST'])
def api_search():
    d = request.get_json() or {}
    q = d.get('q', '').strip()
    if not q:
        return jsonify({'ok': False, 'msg': 'اكتب حاجة'}), 400
    results = []
    u = User.query.filter_by(card_number=q).first()
    if u:
        results.append(u.to_dict())
    else:
        for x in User.query.filter(User.name.contains(q)).all() + User.query.filter(User.phone.contains(q)).all():
            if not any(r['id'] == x.id for r in results):
                results.append(x.to_dict())
    if not results:
        return jsonify({'ok': False, 'msg': 'مفيش نتائج'}), 404
    return jsonify({'ok': True, 'results': results})


@app.route('/api/check-card', methods=['POST'])
def api_check():
    d = request.get_json() or {}
    card = d.get('card_number', '').strip()
    u = User.query.filter_by(card_number=card).first()
    if not u:
        return jsonify({'ok': False, 'msg': 'الرقم غير مسجل'}), 404
    info = u.to_dict()
    last = RenewalRequest.query.filter_by(card_number=card).order_by(RenewalRequest.created_at.desc()).first()
    if last:
        info['last_status'] = last.status
        info['last_amount'] = last.amount or 0
    return jsonify({'ok': True, 'user': info})


@app.route('/api/register', methods=['POST'])
def api_register():
    d = request.get_json() or {}
    name = d.get('name', '').strip()
    card = d.get('card_number', '').strip()
    if not name or not card:
        return jsonify({'ok': False, 'msg': 'اكمل البيانات'}), 400
    u = User.query.filter_by(card_number=card).first()
    if u:
        u.name = name
    else:
        db.session.add(User(card_number=card, name=name, expiry=datetime.now().date()))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/renew', methods=['POST'])
def api_renew():
    card = request.form.get('card_number', '').strip()
    months = int(request.form.get('months', 1))
    from_phone = request.form.get('from_phone', '').strip()
    if not card or not from_phone:
        return jsonify({'ok': False, 'msg': 'اكمل البيانات'}), 400
    if RenewalRequest.query.filter_by(card_number=card, status='pending').first():
        return jsonify({'ok': False, 'msg': 'فيه طلب معلق'}), 400
    u = User.query.filter_by(card_number=card).first()
    fn = None
    if 'screenshot' in request.files:
        f = request.files['screenshot']
        if f and f.filename:
            ext = f.filename.rsplit('.', 1)[-1].lower()
            if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
                fn = secure_filename(card + "_" + str(int(datetime.now().timestamp())) + "." + ext)
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
    db.session.add(RenewalRequest(card_number=card,
                                   name=u.name if u else '',
                                   months=months, from_phone=from_phone,
                                   screenshot=fn))
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم الإرسال'})


@app.route('/api/channels')
def api_channels():
    return jsonify([c.to_dict() for c in Channel.query.all()])


@app.route('/api/channel-issue', methods=['POST'])
def api_channel_issue():
    d = request.get_json() or {}
    if not d.get('channel_id') or not d.get('message'):
        return jsonify({'ok': False, 'msg': 'اكتب المشكلة'}), 400
    ch = Channel.query.get(d['channel_id'])
    if not ch:
        return jsonify({'ok': False, 'msg': 'القناة مش موجودة'}), 404
    db.session.add(ChannelIssue(channel_id=ch.id, channel_name=ch.name,
                                 customer_name=d.get('name', ''),
                                 card_number=d.get('card_number', ''),
                                 phone=d.get('phone', ''),
                                 message=d['message']))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/support', methods=['POST'])
def api_support():
    return jsonify({'ok': True})


@app.route('/uploads/<filename>')
def uploaded(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        a = Admin.query.filter_by(username=u).first()
        if a and check_password_hash(a.password_hash, p):
            session['admin_id'] = a.id
            session['admin_name'] = a.name
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
    return render_template('admin.html', admin_name=session['admin_name'])


@app.route('/api/admin/requests')
def adm_requests():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    return jsonify([r.to_dict() for r in RenewalRequest.query.order_by(RenewalRequest.created_at.desc()).all()])


@app.route('/api/admin/users')
def adm_users():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    return jsonify([u.to_dict() for u in User.query.order_by(User.id.desc()).all()])


@app.route('/api/admin/channels')
def adm_channels():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    return jsonify([c.to_dict() for c in Channel.query.all()])


@app.route('/api/admin/issues')
def adm_issues():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    return jsonify([i.to_dict() for i in ChannelIssue.query.order_by(ChannelIssue.created_at.desc()).all()])


@app.route('/api/admin/stats')
def adm_stats():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    users = User.query.all()
    active = sum(1 for u in users if u.expiry and u.expiry > datetime.now().date())
    return jsonify({
        'users': len(users), 'active': active,
        'pending': RenewalRequest.query.filter_by(status='pending').count(),
        'channels': Channel.query.count(),
        'issues': ChannelIssue.query.count(),
        'money': round(sum(r.amount or 0 for r in RenewalRequest.query.filter_by(status='approved').all()), 2)
    })


@app.route('/api/admin/add_user', methods=['POST'])
def adm_add_user():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    d = request.get_json() or {}
    card = d.get('card_number', '').strip()
    if not card: return jsonify({'ok': False, 'msg': 'اكتب الرقم'}), 400
    if User.query.filter_by(card_number=card).first():
        return jsonify({'ok': False, 'msg': 'موجود'}), 400
    try: exp = datetime.strptime(d.get('expiry', ''), '%Y-%m-%d').date()
    except: exp = datetime.now().date() + timedelta(days=30)
    db.session.add(User(card_number=card, name=d.get('name', ''),
                         phone=d.get('phone', ''), expiry=exp))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/edit_user', methods=['POST'])
def adm_edit_user():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    d = request.get_json() or {}
    u = User.query.filter_by(card_number=d.get('card_number', '')).first()
    if not u: return jsonify({'ok': False}), 404
    if d.get('name') is not None: u.name = d['name']
    if d.get('phone') is not None: u.phone = d['phone']
    if d.get('expiry'):
        try: u.expiry = datetime.strptime(d['expiry'], '%Y-%m-%d').date()
        except: pass
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/del_user/<card>', methods=['DELETE'])
def adm_del_user(card):
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    u = User.query.filter_by(card_number=card).first()
    if u: db.session.delete(u); db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/add_bulk_channels', methods=['POST'])
def adm_bulk():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    n = 0
    for i in range(1, 51):
        name = f"Star Sport {i}"
        if not Channel.query.filter_by(name=name).first():
            db.session.add(Channel(name=name))
            n += 1
    db.session.commit()
    return jsonify({'ok': True, 'added': n})


@app.route('/api/admin/add_channel', methods=['POST'])
def adm_add_ch():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    d = request.get_json() or {}
    if not d.get('name'): return jsonify({'ok': False}), 400
    try: p = float(d.get('price', 0))
    except: p = 0
    db.session.add(Channel(name=d['name'], price=p, problem=d.get('problem', '')))
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/edit_channel', methods=['POST'])
def adm_edit_ch():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    d = request.get_json() or {}
    c = Channel.query.get(d.get('id'))
    if not c: return jsonify({'ok': False}), 404
    if 'name' in d: c.name = d['name']
    if 'price' in d:
        try: c.price = float(d['price'])
        except: pass
    if 'problem' in d: c.problem = d['problem']
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/del_channel/<int:id>', methods=['DELETE'])
def adm_del_ch(id):
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    c = Channel.query.get(id)
    if c: db.session.delete(c); db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/del_issue/<int:id>', methods=['DELETE'])
def adm_del_issue(id):
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    i = ChannelIssue.query.get(id)
    if i: db.session.delete(i); db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/handle', methods=['POST'])
def adm_handle():
    if 'admin_id' not in session: return jsonify({'ok': False}), 401
    d = request.get_json() or {}
    r = RenewalRequest.query.get(d.get('id'))
    if not r: return jsonify({'ok': False}), 404
    if d.get('action') == 'approve':
        try: amt = float(d.get('amount', 0))
        except: amt = 0
        r.amount = amt
        u = User.query.filter_by(card_number=r.card_number).first()
        if u:
            base = u.expiry if u.expiry and u.expiry > datetime.now().date() else datetime.now().date()
            u.expiry = base + timedelta(days=30 * r.months)
            u.last_amount = amt
            if r.from_phone: u.phone = r.from_phone
        else:
            db.session.add(User(card_number=r.card_number, name=r.name or 'مشترك',
                                 phone=r.from_phone or '',
                                 expiry=datetime.now().date() + timedelta(days=30 * r.months),
                                 last_amount=amt))
        r.status = 'approved'
    else:
        r.status = 'rejected'
    db.session.commit()
    return jsonify({'ok': True})


@app.before_request
def init_db():
    if not getattr(app, '_init', False):
        db.create_all()
        if not Admin.query.first():
            db.session.add(Admin(username='admin',
                                  password_hash=generate_password_hash('Star@2026'),
                                  name='المدير'))
        db.session.commit()
        app._init = True


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
