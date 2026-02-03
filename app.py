from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
import jwt
import datetime
from functools import wraps
from config import Config
from models import db, KtpRecord, User

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
db.init_app(app)

@app.route('/healthz', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.filter_by(id=data['user_id']).first()
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Could not verify'}), 401
    
    user = User.query.filter_by(username=data['username']).first()
    
    if user and check_password_hash(user.password, data['password']):
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({'token': token})
    
    return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/auth/register', methods=['POST'])
def register():
    # Helper endpoint to create users (optional but good for testing)
    data = request.get_json()
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')
    new_user = User(username=data['username'], password=hashed_password)
    db.session.add(new_user)
    try:
        db.session.commit()
        return jsonify({'message': 'New user created!'})
    except:
        db.session.rollback()
        return jsonify({'message': 'User already exists'}), 400

@app.route('/api/ktp', methods=['GET'])
@token_required
def get_all_ktp(current_user):
    # Server-side processing for DataTables
    draw = request.args.get('draw', type=int)
    
    # If not a DataTables request, fall back to simple list (backward compatibility)
    if draw is None:
        ktp_records = KtpRecord.query.all()
        output = [ktp.to_dict() for ktp in ktp_records]
        return jsonify({'ktp_records': output})

    start = request.args.get('start', type=int, default=0)
    length = request.args.get('length', type=int, default=10)
    search_value = request.args.get('search[value]', type=str, default='')
    
    # Base query
    query = KtpRecord.query
    total_records = query.count()
    
    # Search/Filtering
    if search_value:
        search_pattern = f"%{search_value}%"
        query = query.filter(or_(
            KtpRecord.full_name.ilike(search_pattern),
            KtpRecord.nik.ilike(search_pattern),
            KtpRecord.address.ilike(search_pattern)
        ))
    
    filtered_records = query.count()
    
    # Sorting
    # Handle DataTables ordering
    order_column_index = request.args.get('order[0][column]', type=int)
    order_dir = request.args.get('order[0][dir]', type=str)
    
    # Map column index to model field (adjust indices based on frontend table columns)
    # 0: nik, 1: full_name, 2: gender, 3: birth_date, 4: address
    columns = [KtpRecord.nik, KtpRecord.full_name, KtpRecord.gender, KtpRecord.birth_date, KtpRecord.address]
    
    if order_column_index is not None and 0 <= order_column_index < len(columns):
        order_col = columns[order_column_index]
        if order_dir == 'desc':
            query = query.order_by(order_col.desc())
        else:
            query = query.order_by(order_col.asc())
    else:
        # Default sort (Deterministic)
        query = query.order_by(KtpRecord.updated_at.desc(), KtpRecord.nik.asc())
    
    # Pagination
    if length != -1: # -1 means show all
        query = query.offset(start).limit(length)
    
    ktp_records = query.all()
    data = [ktp.to_dict() for ktp in ktp_records]
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': filtered_records,
        'data': data
    })

@app.route('/api/ktp/<nik>', methods=['GET'])
@token_required
def get_one_ktp(current_user, nik):
    ktp = KtpRecord.query.filter_by(nik=nik).first()
    if not ktp:
        return jsonify({'message': 'No KTP found!'}), 404
    return jsonify({'ktp_record': ktp.to_dict()})

@app.route('/api/ktp', methods=['POST'])
@token_required
def create_ktp(current_user):
    data = request.get_json()
    
    try:
        new_ktp = KtpRecord(
            nik=data['nik'],
            full_name=data['full_name'],
            birth_place=data['birth_place'],
            birth_date=datetime.datetime.strptime(data['birth_date'], '%Y-%m-%d').date(),
            gender=data.get('gender'),
            blood_type=data.get('blood_type'),
            address=data['address'],
            rt_rw=data.get('rt_rw'),
            village_kelurahan=data.get('village_kelurahan'),
            district_kecamatan=data.get('district_kecamatan'),
            religion=data.get('religion'),
            marital_status=data.get('marital_status'),
            occupation=data.get('occupation'),
            citizenship=data.get('citizenship', 'WNI'),
            expiry_date=data.get('expiry_date', 'SEUMUR HIDUP')
        )
        db.session.add(new_ktp)
        db.session.commit()
        return jsonify({'message': 'KTP record created!', 'ktp_record': new_ktp.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

@app.route('/api/ktp/<nik>', methods=['PUT'])
@token_required
def update_ktp(current_user, nik):
    ktp = KtpRecord.query.filter_by(nik=nik).first()
    if not ktp:
        return jsonify({'message': 'No KTP found!'}), 404
    
    data = request.get_json()
    
    try:
        ktp.full_name = data.get('full_name', ktp.full_name)
        ktp.birth_place = data.get('birth_place', ktp.birth_place)
        if 'birth_date' in data:
            ktp.birth_date = datetime.datetime.strptime(data['birth_date'], '%Y-%m-%d').date()
        ktp.gender = data.get('gender', ktp.gender)
        ktp.blood_type = data.get('blood_type', ktp.blood_type)
        ktp.address = data.get('address', ktp.address)
        ktp.rt_rw = data.get('rt_rw', ktp.rt_rw)
        ktp.village_kelurahan = data.get('village_kelurahan', ktp.village_kelurahan)
        ktp.district_kecamatan = data.get('district_kecamatan', ktp.district_kecamatan)
        ktp.religion = data.get('religion', ktp.religion)
        ktp.marital_status = data.get('marital_status', ktp.marital_status)
        ktp.occupation = data.get('occupation', ktp.occupation)
        ktp.citizenship = data.get('citizenship', ktp.citizenship)
        ktp.expiry_date = data.get('expiry_date', ktp.expiry_date)
        
        db.session.commit()
        return jsonify({'message': 'KTP record updated!', 'ktp_record': ktp.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

@app.route('/api/ktp/<nik>', methods=['DELETE'])
@token_required
def delete_ktp(current_user, nik):
    ktp = KtpRecord.query.filter_by(nik=nik).first()
    if not ktp:
        return jsonify({'message': 'No KTP found!'}), 404
    
    db.session.delete(ktp)
    db.session.commit()
    return jsonify({'message': 'KTP record deleted!'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create a default user if not exists
        if not User.query.filter_by(username='admin').first():
            hashed_password = generate_password_hash('admin123', method='pbkdf2:sha256')
            admin = User(username='admin', password=hashed_password)
            db.session.add(admin)
            db.session.commit()
            print("Admin user created (admin/admin123)")
    app.run(host='0.0.0.0', port=5000)
