from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models import User, ParkingLot, ParkingSpot, Reservation
from app.forms import LoginForm, RegistrationForm, ParkingLotForm, SelectLotForm, ReleaseSpotForm
from datetime import datetime, timedelta

bp = Blueprint('main', __name__)

# --- Core Routes ---
@bp.route('/')
@bp.route('/index')
def index():
    parking_lots = ParkingLot.query.all()
    return render_template('index.html', title='Welcome', parking_lots=parking_lots)

# --- Authentication Routes ---
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('main.admin_dashboard'))
        else:
            return redirect(url_for('main.user_dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash(f'Login successful for {user.username}', 'success')
            # Redirect admin and user to different dashboards
            if user.is_admin:
                next_page = request.args.get('next')
                return redirect(next_page or url_for('main.admin_dashboard'))
            else:
                next_page = request.args.get('next')
                return redirect(next_page or url_for('main.user_dashboard'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index')) # Or user dashboard
    form = RegistrationForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
             flash('Username already exists. Please choose a different one.', 'warning')
             return render_template('register.html', title='Register', form=form)
        user = User(username=form.username.data)
        user.set_password(form.password.data) # Hash password
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', title='Register', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

# --- Admin Routes ---
@bp.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access restricted to administrators.', 'danger')
        return redirect(url_for('main.index'))
        
    parking_lots = ParkingLot.query.all()
    users = User.query.filter_by(is_admin=False).all()  # Get non-admin users
    
    # Calculate spending totals for each user
    user_spending = {}
    for user in users:
        total_spent = db.session.query(db.func.sum(Reservation.parking_cost)).filter(
            Reservation.user_id == user.id,
            Reservation.parking_cost != None
        ).scalar()
        user_spending[user.id] = float(total_spent) if total_spent is not None else 0.0
    
    # Aggregate spot status data for dashboard/charts
    lot_stats = []
    for lot in parking_lots:
        total_spots = lot.maximum_number_of_spots
        occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
        available_spots = total_spots - occupied_spots  # Or query for 'A'
        lot_stats.append({
            'name': lot.prime_location_name,
            'total': total_spots,
            'occupied': occupied_spots,
            'available': available_spots,
            'id': lot.id
        })

    return render_template('admin_dashboard.html', title='Admin Dashboard', lot_stats=lot_stats, users=users, user_spending=user_spending)


@bp.route('/admin/lot/new', methods=['GET', 'POST'])
@login_required
def create_parking_lot():
    if not current_user.is_admin: return redirect(url_for('main.index'))
    form = ParkingLotForm()
    if form.validate_on_submit():
        parking_lot = ParkingLot(
            prime_location_name=form.prime_location_name.data,
            price=form.price.data,
            address=form.address.data,
            pin_code=form.pin_code.data,
            maximum_number_of_spots=form.maximum_number_of_spots.data
        )
        db.session.add(parking_lot)
        db.session.flush() # Get the ID for the new lot before commit

        # Create the parking spots automatically
        for i in range(1, form.maximum_number_of_spots.data + 1):
            # Simple spot identifier, e.g., Spot-1, Spot-2...
            spot = ParkingSpot(spot_identifier=f'Spot-{i}', lot_id=parking_lot.id, status='A')
            db.session.add(spot)

        db.session.commit()
        flash('Parking lot and spots created successfully!', 'success')
        return redirect(url_for('main.admin_dashboard'))
    return render_template('create_edit_lot.html', title='Create Parking Lot', form=form, legend='New Parking Lot')

@bp.route('/admin/lot/<int:lot_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_parking_lot(lot_id):
    if not current_user.is_admin: return redirect(url_for('main.index'))
    parking_lot = ParkingLot.query.get_or_404(lot_id)
    # Store original number of spots
    original_spot_count = parking_lot.maximum_number_of_spots
    form = ParkingLotForm(obj=parking_lot) # Pre-populate form

    if form.validate_on_submit():
        # Update lot details
        parking_lot.prime_location_name = form.prime_location_name.data
        parking_lot.price = form.price.data
        parking_lot.address = form.address.data
        parking_lot.pin_code = form.pin_code.data
        new_spot_count = form.maximum_number_of_spots.data
        parking_lot.maximum_number_of_spots = new_spot_count

        # Adjust number of spots
        spot_diff = new_spot_count - original_spot_count

        if spot_diff > 0: # Add new spots
            # Find the highest existing spot number to continue sequence
            last_spot_num = 0
            existing_spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
            for spot in existing_spots:
                 try:
                      num = int(spot.spot_identifier.split('-')[-1])
                      if num > last_spot_num:
                           last_spot_num = num
                 except:
                      pass # Handle non-standard identifiers if necessary

            for i in range(spot_diff):
                new_spot_id_num = last_spot_num + 1 + i
                new_spot = ParkingSpot(spot_identifier=f'Spot-{new_spot_id_num}', lot_id=parking_lot.id, status='A')
                db.session.add(new_spot)
        elif spot_diff < 0: # Remove spots (only if available)
            spots_to_remove = abs(spot_diff)
            available_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').order_by(ParkingSpot.id.desc()).limit(spots_to_remove).all()
            if len(available_spots) < spots_to_remove:
                flash('Cannot reduce spots. Not enough available spots to remove.', 'danger')
                db.session.rollback() # Rollback changes if spots cannot be removed
                return render_template('create_edit_lot.html', title='Edit Parking Lot', form=form, legend=f'Edit Lot: {parking_lot.prime_location_name}', lot=parking_lot)
            else:
                for spot in available_spots:
                    db.session.delete(spot)

        db.session.commit()
        flash('Parking lot updated successfully!', 'success')
        return redirect(url_for('main.admin_dashboard'))

    return render_template('create_edit_lot.html', title='Edit Parking Lot', form=form, legend=f'Edit Lot: {parking_lot.prime_location_name}', lot=parking_lot)


@bp.route('/admin/lot/<int:lot_id>/delete', methods=['POST'])
@login_required
def delete_parking_lot(lot_id):
    if not current_user.is_admin: return redirect(url_for('main.index'))
    parking_lot = ParkingLot.query.get_or_404(lot_id)
    # Check if all spots are empty (Available)
    occupied_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='O').count()
    if occupied_spots > 0:
        flash('Cannot delete lot. Some spots are still occupied.', 'danger')
    else:
        # Cascade delete should handle spots and reservations due to model setup
        db.session.delete(parking_lot)
        db.session.commit()
        flash('Parking lot deleted successfully!', 'success')
    return redirect(url_for('main.admin_dashboard'))

@bp.route('/admin/lot/<int:lot_id>/spots')
@login_required
def view_lot_spots(lot_id):
    if not current_user.is_admin: return redirect(url_for('main.index'))
    parking_lot = ParkingLot.query.get_or_404(lot_id)
    # Join Reservation data to show user if occupied
    spots = db.session.query(ParkingSpot, User.username).\
        outerjoin(Reservation, ParkingSpot.reservation).\
        outerjoin(User, Reservation.user).\
        filter(ParkingSpot.lot_id == lot_id).all()

    # Reformat spots data for easier template access
    spot_details = []
    for spot, username in spots:
         spot_details.append({
              'id': spot.id,
              'identifier': spot.spot_identifier,
              'status': spot.status,
              'username': username if spot.status == 'O' else None # Show username only if occupied
         })
    return render_template('view_spots.html', title=f'Spots in {parking_lot.prime_location_name}', lot=parking_lot, spots=spot_details)

@bp.route('/admin/spot/<int:spot_id>/delete', methods=['POST'])
@login_required
def delete_parking_spot(spot_id):
    if not current_user.is_admin: return redirect(url_for('main.index'))
    spot = ParkingSpot.query.get_or_404(spot_id)
    lot_id = spot.lot_id # Get lot_id before deleting for redirect
    if spot.status == 'O':
        flash('Cannot delete an occupied spot.', 'danger')
    else:
        # Also update the max count in the parent lot
        parking_lot = ParkingLot.query.get(spot.lot_id)
        if parking_lot:
            parking_lot.maximum_number_of_spots = max(0, parking_lot.maximum_number_of_spots - 1)

        db.session.delete(spot)
        db.session.commit()
        flash('Parking spot deleted successfully!', 'success')
    # Redirect back to the view spots page for the same lot
    return redirect(url_for('main.view_lot_spots', lot_id=lot_id))


# --- User Routes ---
@bp.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.is_admin: # Admins shouldn't use the user dashboard
        return redirect(url_for('main.admin_dashboard'))

    # Find current reservation for the user, if any
    current_reservation = Reservation.query.filter_by(user_id=current_user.id, leaving_timestamp=None).first()
    # Get available lots for booking
    parking_lots = ParkingLot.query.all() # Or filter based on availability if needed
    # Dynamically generate choice text with correct pricing
    lot_choices = [
        (lot.id, f"{lot.prime_location_name} (₹{lot.price:.0f} first hour, ₹{lot.price / 2.0:.0f} each additional)")
        for lot in parking_lots
    ]

    select_form = SelectLotForm()
    select_form.parking_lot.choices = lot_choices

    release_form = ReleaseSpotForm()
    if current_reservation:
         release_form.reservation_id.data = current_reservation.id

    # Get user's parking history
    parking_history = Reservation.query.filter_by(user_id=current_user.id).order_by(Reservation.parking_timestamp.desc()).all()

    # Calculate total spent directly from the database
    total_spent_result = db.session.query(db.func.sum(Reservation.parking_cost)).filter(
        Reservation.user_id == current_user.id,
        Reservation.parking_cost != None
    ).scalar()

    # Ensure we have a valid number, not None
    total_spent = float(total_spent_result) if total_spent_result is not None else 0.0

    return render_template('user_dashboard.html',
                           title='User Dashboard',
                           select_form=select_form,
                           release_form=release_form,
                           current_reservation=current_reservation,
                           parking_history=parking_history,
                           total_spent=total_spent,
                           IST_OFFSET=5.5, # Pass offset to template
                           timedelta=timedelta # Pass timedelta for calculations
                           )

@bp.route('/book_spot', methods=['POST'])
@login_required
def book_spot():
    if current_user.is_admin: return redirect(url_for('main.index'))

    # Check if user already has an active reservation
    if Reservation.query.filter_by(user_id=current_user.id, leaving_timestamp=None).first():
        flash('You already have an active parking reservation.', 'warning')
        return redirect(url_for('main.user_dashboard'))

    form = SelectLotForm()
    # Need to populate choices again as they are lost on POST if validation fails
    parking_lots = ParkingLot.query.all()
    # Dynamically generate choice text with correct pricing
    form.parking_lot.choices = [
        (lot.id, f"{lot.prime_location_name} (₹{lot.price:.0f} first hour, ₹{lot.price / 2.0:.0f} each additional)")
        for lot in parking_lots
    ]

    if form.validate_on_submit():
        selected_lot_id = form.parking_lot.data
        # Find the first available spot in the selected lot
        available_spot = ParkingSpot.query.filter_by(lot_id=selected_lot_id, status='A').order_by(ParkingSpot.id).first()

        if available_spot:
            # Update spot status
            available_spot.status = 'O'
            # Create reservation record
            reservation = Reservation(
                spot_id=available_spot.id,
                user_id=current_user.id,
                parking_timestamp=datetime.utcnow()
                # Cost will be calculated on release
            )
            db.session.add(reservation)
            db.session.commit()
            flash(f'Successfully booked spot {available_spot.spot_identifier} in lot {available_spot.parking_lot.prime_location_name}!', 'success')
        else:
            flash('Sorry, no available spots in the selected lot.', 'warning')
    else:
         # Handle form validation errors if any (though less likely with just a select field)
         flash('Please select a valid parking lot.', 'danger')

    return redirect(url_for('main.user_dashboard'))


@bp.route('/release_spot', methods=['POST'])
@login_required
def release_spot():
    if current_user.is_admin:
        return redirect(url_for('main.index'))

    form = ReleaseSpotForm() # Primarily used for CSRF token here
    if form.validate_on_submit(): # Check CSRF token
        reservation = Reservation.query.filter_by(user_id=current_user.id, leaving_timestamp=None).first()

        if reservation:
            spot = ParkingSpot.query.get(reservation.spot_id)
            # Ensure spot and lot exist before proceeding
            if not spot or not spot.parking_lot:
                 flash('Error: Associated spot or parking lot not found.', 'danger')
                 return redirect(url_for('main.user_dashboard'))

            parking_lot = spot.parking_lot # Get the parking lot from the spot
            base_rate = parking_lot.price # Use the lot's specific price
            additional_rate = base_rate / 2.0 # Calculate additional rate as half the base rate

            # Update timestamps and calculate cost
            reservation.leaving_timestamp = datetime.utcnow()
            time_parked = reservation.leaving_timestamp - reservation.parking_timestamp
            hours_parked = time_parked.total_seconds() / 3600

            # Calculate cost based on the lot's rates
            if hours_parked <= 1:
                cost = base_rate # Minimum charge is the base rate
            else:
                # First hour costs base_rate, additional hours cost additional_rate each
                additional_hours = int(hours_parked)
                if hours_parked > int(hours_parked):  # If there's a partial hour
                    additional_hours += 1  # Round up to the next hour
                # Ensure we don't calculate negative additional hours if exactly 1 hour
                additional_hours_count = max(0, additional_hours - 1)
                cost = base_rate + (additional_hours_count * additional_rate)

            # Store the calculated cost - ensure it's a float
            print(f"DEBUG: Setting parking cost to {cost} (type: {type(cost).__name__})")
            reservation.parking_cost = float(cost)
            spot.status = 'A'

            db.session.commit()

            # Create a more descriptive message about the pricing
            if hours_parked <= 1:
                pricing_detail = f"₹{base_rate:.2f} minimum charge (first hour or less)"
            else:
                additional_hours_detail = int(hours_parked)
                if hours_parked > int(hours_parked):
                    additional_hours_detail += 1
                additional_hours_count_msg = max(0, additional_hours_detail - 1) # For message consistency
                pricing_detail = f"₹{base_rate:.2f} first hour + ₹{additional_rate:.2f} × {additional_hours_count_msg} additional hours"

            flash(f'Spot {spot.spot_identifier} released. Total cost: ₹{reservation.parking_cost:.2f} ({pricing_detail})', 'success')
        else:
            flash('No active reservation found to release.', 'warning')

    return redirect(url_for('main.user_dashboard'))

# --- Admin User Management Routes ---
@bp.route('/admin/user/<int:user_id>', methods=['GET'])
@login_required
def view_user_details(user_id):
    if not current_user.is_admin:
        flash('Access restricted to administrators.', 'danger')
        return redirect(url_for('main.index'))
    
    user = User.query.get_or_404(user_id)
    
    # Ensure any datetime objects are timezone-naive for template handling
    if user.created_at and user.created_at.tzinfo:
        user.created_at = user.created_at.replace(tzinfo=None)
    
    # Calculate total spent
    total_spent = 0
    for reservation in user.reservations:
        if reservation.parking_cost is not None:
            total_spent += float(reservation.parking_cost)
        
        # Make timestamp timezone-naive for template handling
        if reservation.parking_timestamp and reservation.parking_timestamp.tzinfo:
            reservation.parking_timestamp = reservation.parking_timestamp.replace(tzinfo=None)
        if reservation.leaving_timestamp and reservation.leaving_timestamp.tzinfo:
            reservation.leaving_timestamp = reservation.leaving_timestamp.replace(tzinfo=None)
    
    # Get active reservations
    active_reservations = [r for r in user.reservations if r.leaving_timestamp is None]    # Get completed reservations with all details
    completed_reservations = db.session.query(
        Reservation.parking_timestamp,
        Reservation.leaving_timestamp,
        Reservation.parking_cost,
        ParkingSpot.spot_identifier,
        ParkingLot.prime_location_name
    ).join(ParkingSpot, Reservation.spot_id == ParkingSpot.id)\
        .join(ParkingLot, ParkingSpot.lot_id == ParkingLot.id)\
        .filter(Reservation.user_id == user_id)\
        .filter(Reservation.leaving_timestamp != None)\
        .order_by(Reservation.parking_timestamp.desc())\
        .all()
    
    return render_template('user_details.html', 
                          title=f'User Details - {user.username}',
                          user=user,
                          total_spent=total_spent,
                          active_reservations=active_reservations,
                          completed_reservations=completed_reservations)

@bp.route('/admin/user/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('Access restricted to administrators.', 'danger')
        return redirect(url_for('main.index'))
    
    user = User.query.get_or_404(user_id)
    
    # Don't allow deleting admin users
    if user.is_admin:
        flash('Cannot delete administrator accounts.', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    
    username = user.username
    
    # Delete the user - this will cascade delete their reservations due to 
    # the cascade setting in the User model
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User "{username}" and all their data have been deleted.', 'success')
    return redirect(url_for('main.admin_dashboard'))