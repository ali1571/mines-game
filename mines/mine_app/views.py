#import random
#from django.shortcuts import render
#from django.views.decorators.http import require_POST
#from django.http import HttpResponse
#from django.contrib.auth import authenticate, login, login, get_user_model
#from django.shortcuts import render
#from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP# Add this import
from .models import GameLog
from django.utils import timezone
from django.shortcuts import redirect
from .utils import get_client_ip, get_device_type
from django_ratelimit.decorators import ratelimit
from django.db import transaction

MULTIPLIERS = [2.0, 4.0, 2.80, 3.50, 4.0, 6.0]



# REMOVE THIS LINE from the home/board view
def home(request):
    context = {'range': range(9)}

    if request.user.is_authenticated:
        context['user_stats'] = request.user.get_game_stats()

    if request.user.is_authenticated and not request.user.is_verified:
        context['show_kyc_form'] = True

    if request.user.is_authenticated and request.session.get('game_active'):
        context['restored_game'] = True
        context['revealed_tiles'] = request.session.get('revealed_tiles', [])
        context['mine_locations'] = request.session.get('mine_locations', [])
        context['active_bet'] = request.session.get('active_bet', '0')

    return render(request, 'mines/board.html', context)

from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.views.decorators.http import require_http_methods, require_POST

User = get_user_model()
@require_http_methods(["GET", "POST"])
def login_view(request):
    """Show the initial username entry form"""
    return render(request, 'mines/partials/login_modal.html')


@require_POST
def check_username(request):
    """Check if username exists and route to appropriate step"""
    username = request.POST.get('username', '').strip()

    if not username:
        return HttpResponse(
            '<div id="username-error" hx-swap-oob="true" class="text-red-400 text-xs font-medium">Username is required</div>'
        )

    if len(username) < 3:
        return HttpResponse(
            '<div id="username-error" hx-swap-oob="true" class="text-red-400 text-xs font-medium">Username must be at least 3 characters</div>'
        )

    # Check if user exists
    user_exists = User.objects.filter(username=username).exists()

    if user_exists:
        # Existing user - show login form
        return render(request, 'mines/partials/password_step.html', {
            'username': username
        })
    else:
        # New user - show signup form
        return render(request, 'mines/partials/signup_step.html', {
            'username': username
        })

@ratelimit(key='ip', rate='5/d', method='POST')
@require_POST
def login_submit(request):
    """Handle login submission"""
    username = request.POST.get('username')
    password = request.POST.get('password')

    user = authenticate(request, username=username, password=password)

    if user is None:
        return HttpResponse(
            '<div id="auth-error" hx-swap-oob="true" class="text-red-400 text-xs font-medium bg-red-500/10 border-l-4 border-red-500 px-3 py-2 rounded-r-lg">Incorrect password</div>'
        )

    login(request, user)
    request.session.cycle_key()

    # Redirect to home
    response = HttpResponse()
    response['HX-Redirect'] = '/'
    return response


@require_POST
def signup_submit(request):
    """Handle signup submission"""
    username = request.POST.get('username')
    password = request.POST.get('password')
    password_confirm = request.POST.get('password_confirm')

    # Validate passwords match
    if password != password_confirm:
        return HttpResponse(
            '<div id="auth-error" hx-swap-oob="true" class="text-red-400 text-xs font-medium bg-red-500/10 border-l-4 border-red-500 px-3 py-2 rounded-r-lg">Passwords do not match</div>'
        )

    # Check if username was taken in the meantime (race condition)
    if User.objects.filter(username=username).exists():
        return HttpResponse(
            '<div id="auth-error" hx-swap-oob="true" class="text-red-400 text-xs font-medium bg-red-500/10 border-l-4 border-red-500 px-3 py-2 rounded-r-lg">Username taken. Please go back and choose another.</div>'
        )

    # Create user
    user = User.objects.create_user(username=username, password=password)
    login(request, user)
    request.session.cycle_key()

    # Redirect to home
    response = HttpResponse()
    response['HX-Redirect'] = '/'
    return response


from django.http import HttpResponse
from django.shortcuts import render
from PIL import Image
import magic
import uuid
from django.contrib.auth import get_user_model
import re

def submit_kyc(request):
    user = request.user

    if user.is_verified:
        return render(request, 'mines/partials/wallet_modal.html', {'message': 'You are already verified'})

    has_submitted_kyc = all([user.phone_number, user.cnic_front, user.cnic_back])

    if request.method == "POST":
        if has_submitted_kyc:
            return render(request, 'mines/partials/kyc_pending.html', {'message': 'Your KYC is already under review'})

        # 1. Get files
        front_img = request.FILES.get('cnic_front')
        back_img = request.FILES.get('cnic_back')

        if not front_img or not back_img:
            return HttpResponse(
                '<div id="general-error" hx-swap-oob="true" class="text-red-500 text-xs">Please upload both sides of your CNIC</div>')

        # 2. Validation Helper Function to prevent repetition
        def validate_file(file):
            if file.size > 5 * 1024 * 1024:
                return False, "File too large (Max 5MB)"

            # Read header and IMMEDIATELY seek(0)
            header = file.read(2048)
            file.seek(0)

            mime = magic.from_buffer(header, mime=True)
            if mime not in ['image/jpeg', 'image/png']:
                return False, "Only JPEG and PNG allowed"

            try:
                img = Image.open(file)
                img.verify()
                file.seek(0)  # Reset again after verify()
            except:
                return False, "Corrupted image"

            return True, mime

        # Validate Front
        valid_front, front_res = validate_file(front_img)
        if not valid_front:
            return HttpResponse(
                f'<div id="general-error" hx-swap-oob="true" class="text-red-500 text-xs">{front_res} (Front)</div>')

        # Validate Back
        valid_back, back_res = validate_file(back_img)
        if not valid_back:
            return HttpResponse(
                f'<div id="general-error" hx-swap-oob="true" class="text-red-500 text-xs">{back_res} (Back)</div>')

        # 3. Sanitize Names
        front_ext = 'jpg' if front_res == 'image/jpeg' else 'png'
        back_ext = 'jpg' if back_res == 'image/jpeg' else 'png'
        front_img.name = f"{uuid.uuid4()}.{front_ext}"
        back_img.name = f"{uuid.uuid4()}.{back_ext}"

        # 4. Save Data
        try:
            cnic_number = request.POST.get('cnic_number', '').strip()
            User = get_user_model()
            if User.objects.filter(cnic_number=cnic_number).exclude(id=user.id).exists():
                return HttpResponse(
                    '<div id="general-error" hx-swap-oob="true" class="text-red-500 text-xs">CNIC already registered</div>')

            user.phone_number = request.POST.get('phone', '').strip()
            user.first_name = request.POST.get('firstname', '').strip()
            user.last_name = request.POST.get('lastname', '').strip()
            user.cnic_number = cnic_number
            user.cnic_front = front_img
            user.cnic_back = back_img
            user.is_verified = False

            user.save()

            return render(request, 'mines/partials/kyc_pending.html')

        except Exception as e:
            return HttpResponse(
                '<div id="general-error" hx-swap-oob="true" class="text-red-500 text-xs">Server error during upload</div>')

    if has_submitted_kyc and not user.is_verified:
        return render(request, 'mines/partials/kyc_pending.html')

    return render(request, 'mines/partials/kyc_form.html')

import random  # <--- CRUCIAL: Add this at the top!
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect


@ratelimit(key='user', rate='100/h', method='POST')
@csrf_protect
@require_POST
def start_game(request):
    try:
        # 1. AUTH & VERIFICATION GATE
        if not request.user.is_authenticated:
            return render(request, 'mines/partials/login_modal.html')

        #if not request.user.is_verified:
        #    return render(request, 'mines/partials/kyc_pending.html')

        # 2. EXTRACT AND VALIDATE AMOUNT
        try:
            raw_amount = request.POST.get('bet_amount', '0')
            print(f"DEBUG: Received bet_amount raw: '{raw_amount}'")
            bet_amount = Decimal(raw_amount).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        except (ValueError, InvalidOperation):
            return HttpResponse("Invalid Amount", headers={"HX-Retarget": "#bet-error"})

        MIN_BET = Decimal('20')
        MAX_BET = request.user.usdt_balance

        # 3. MINIMUM BET CHECK (Correctly Indented)
        if bet_amount < MIN_BET:
            return HttpResponse("Minimum bet is 20 PKR", headers={"HX-Retarget": "#bet-error"})

        if bet_amount > MAX_BET:
            return HttpResponse("Insufficient funds", headers={"HX-Retarget": "#bet-error"})


        # 4. BALANCE CHECK + DEDUCTION
        # select_for_update() locks this user's DB row until the transaction
        # commits. A second simultaneous request will wait at this line instead
        # of reading the same balance and passing both through.
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            if user.usdt_balance < bet_amount:
                return HttpResponse("Insufficient funds", headers={"HX-Retarget": "#bet-error"})

            # --- VALIDATION PASSED: START GAME LOGIC ---

            # Create game log when game starts
            game_log = GameLog.objects.create(
                user=user,
                bet_amount=bet_amount,
                ip_address=get_client_ip(request),
                device_type=get_device_type(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                outcome='abandoned'
            )

            # Store the game_id in session so we can update it later
            request.session['current_game_id'] = str(game_log.game_id)

            # 5. DEDUCT FUNDS & SET SESSION
            user.usdt_balance -= bet_amount
            user.save()

        request.session['active_bet'] = str(bet_amount)
        request.session['game_active'] = True
        request.session['revealed_tiles'] = []

        # 6. MINE GENERATION
        mine_locations = random.sample(range(9), 3)
        coord_list = [f"({(idx // 3) + 1},{(idx % 3) + 1})" for idx in mine_locations]

        # 7. UPDATE USER & SESSION
        user.active_mine_coords = ", ".join(coord_list)
        user.save()

        request.session['mine_locations'] = mine_locations
        request.session.modified = True

        # 8. RESPONSE & UI UPDATES
        latest_balance = user.usdt_balance
        response = render(request, 'mines/partials/grid.html', {'range': range(9)})

        # UI Updates via OOB
        disabled_button = f'''
            <div id="button-container" hx-swap-oob="true">
                <button disabled class="w-full mt-6 py-4 bg-slate-800 text-slate-500 font-black rounded-xl cursor-not-allowed opacity-50 uppercase">
                    Game in Progress...
                </button>
            </div>
        '''

        balance_update = f'''
            <span id="user-balance" hx-swap-oob="true" class="text-white font-mono font-bold">
                {latest_balance:.2f}
            </span>
        '''

        response.content += (disabled_button + balance_update).encode()
        return response

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return HttpResponse(f"Server Error", status=500)

def game_board(request):
    # 1. Check if logged in
    if not request.user.is_authenticated:
        return HttpResponse("Unauthorized", status=401)

    # 2. Check if verified
    if not request.user.is_verified:
        return HttpResponse("Verification Required", status=403)


    # For now, let's just render the empty board
    # In a real game, you'd save mine_locations in a Session or Database
    grid_size = range(9)
    return render(request, 'mines/board.html', {'grid': grid_size})


@require_POST
@transaction.atomic
def cashout(request):
    if not request.session.get('game_active'):
        return HttpResponse("No active game", status=400)

    revealed_tiles = request.session.get('revealed_tiles', [])
    mine_locations = request.session.get('mine_locations', [])

    if not revealed_tiles:
        return HttpResponse("No gems found", status=400)

    bet_amount = Decimal(request.session.get('active_bet', '0'))

    # Calculate payout
    gems_found = len(revealed_tiles)
    multiplier = Decimal(str(MULTIPLIERS[gems_found - 1]))
    payout = bet_amount * multiplier



    # Update User Balance — transaction.atomic() is on this view, so
    # select_for_update() locks the row while we read, add, and save.
    user = User.objects.select_for_update().get(pk=request.user.pk)
    user.usdt_balance += payout
    user.save()

    # ===== UPDATE GAME LOG =====
    game_id = request.session.get('current_game_id')
    if game_id:
        try:
            game_log = GameLog.objects.get(game_id=game_id)
            game_log.game_end_timestamp = timezone.now()
            game_log.gems_found = gems_found
            game_log.payout_amount = payout
            game_log.multiplier = multiplier
            game_log.outcome = 'win'
            game_log.save()
        except GameLog.DoesNotExist:
            pass

    # End Game
    request.session['game_active'] = False
    request.session['active_bet'] = '0'
    request.session.pop('current_game_id', None)

    # ===== RENDER REVEALED GRID (showing all mines) =====
    response = render(request, 'mines/partials/grid.html', {
        'range': range(9),
        'mine_locations': mine_locations,
        'revealed_tiles': revealed_tiles,
        'cashout_reveal': True,  # Flag to show this is a cashout reveal
        'revealed': True
    })

    # Update balance and show win screen OOB
    oob = f'''
    <span id="user-balance" hx-swap-oob="true">{user.usdt_balance:.2f}</span>
    <div id="button-container" hx-swap-oob="true">
        <button hx-post="/reset/" hx-target="#game-grid" hx-swap="outerHTML"
                class="w-full mt-6 py-4 bg-orange-500 hover:bg-orange-400 text-black font-black rounded-xl transition-all shadow-[0_4px_0_rgb(194,120,3)] active:translate-y-1 uppercase">
            Play Again
        </button>
    </div>
    
    <div id="game-overlay" hx-swap-oob="true">
        <div class="fixed inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center z-50 p-4">
            <div class="text-center bg-slate-900 p-4 rounded-2xl border-2 border-emerald-500 shadow-[0_0_30px_rgba(16,185,129,0.3)] w-full max-w-xs" style="transform: translateY(-96px)">

                <!-- Win heading -->
                <h2 class="text-2xl font-black text-emerald-400 mb-1">CASHED OUT!</h2>

                <!-- Payout -->
                <p class="text-3xl font-black text-white mb-3">Rs {payout:.2f}</p>

                <!-- Stats row -->
                <div class="flex justify-center gap-6 mb-3">
                    <div>
                        <p class="text-[10px] text-slate-500 uppercase font-bold">Gems</p>
                        <p class="text-sm font-bold text-emerald-400">{gems_found}</p>
                    </div>
                    <div>
                        <p class="text-[10px] text-slate-500 uppercase font-bold">Balance</p>
                        <p class="text-sm font-bold text-white">Rs {user.usdt_balance:.2f}</p>
                    </div>
                </div>

                <!-- Close button -->
                <button
                    onclick="document.getElementById('game-overlay').innerHTML = ''"
                    class="w-full bg-emerald-500 hover:bg-emerald-400 text-black font-black py-2 px-4 rounded-xl uppercase text-sm active:scale-95 transition-transform">
                    Close
                </button>

                <script>
                    sound = document.getElementById('sound-win');
                    if (sound) {{
                        sound.currentTime = 0;
                        sound.play().catch(err => console.log('Audio play failed:', err));
                    }}
                </script>
            </div>
        </div>
    </div>
    '''.encode()

    response.content += oob
    return response



@require_POST
@transaction.atomic
def reveal_tile(request, tile_id):
    # 1. Combined Security Check
    if not request.user.is_authenticated:
        return render(request, 'mines/partials/login_modal.html')

    #if not request.user.is_verified:
    #    return HttpResponse("Verification Required", status=403)

    # 2. Game State Check
    if not request.session.get('game_active', False):
        return HttpResponse("Please click 'Bet' to start a new game.", status=400)

    mine_locations = request.session.get('mine_locations', [])
    revealed_tiles = request.session.get('revealed_tiles', [])

    tile_id = int(tile_id)
    if tile_id in revealed_tiles:
        return HttpResponse(status=204)

    # --- 1. LOSS CASE (Hit a Mine) ---
    if tile_id in mine_locations:
        game_id = request.session.get('current_game_id')
        if game_id:
            try:
                game_log = GameLog.objects.get(game_id=game_id)
                game_log.game_end_timestamp = timezone.now()
                game_log.gems_found = len(revealed_tiles)
                game_log.payout_amount = Decimal('0.00')  # Lost - no payout
                game_log.outcome = 'loss'  # Hit a mine

                # Calculate multiplier they WOULD have gotten
                if len(revealed_tiles) > 0:
                    game_log.multiplier = Decimal(str(MULTIPLIERS[len(revealed_tiles) - 1]))

                game_log.save()
            except GameLog.DoesNotExist:
                pass

        request.session['game_active'] = False
        request.session['revealed_tiles'] = []  # Reset for next game

        user = request.user

        # Render the full revealed grid
        response = render(request, 'mines/partials/grid.html', {
            'range': range(9),
            'mine_locations': mine_locations,
            'hit_id': tile_id,
            'revealed': True
        })

        # OOB: Reset the Play Button so they can play again immediately
        # and ensure the wallet target isn't blocked by any lingering overlays
        reset_ui = b'''
        <div id="button-container" hx-swap-oob="true">
            <button hx-post="/start-game/" hx-include="#bet_amount" hx-target="#game-grid"
                    class="w-full mt-6 py-4 bg-orange-500 hover:bg-orange-400 text-black font-black rounded-xl transition-all uppercase">
                Play
            </button>
        </div>
        <div id="game-overlay" hx-swap-oob="true"></div>
        '''
        response.content += reset_ui
        return response

    # --- 2. PROGRESS CASE (Hit a Gem) ---
    revealed_tiles.append(tile_id)
    request.session['revealed_tiles'] = revealed_tiles
    request.session.modified = True

    bet_amount = Decimal(request.session.get('active_bet', '0'))
    gems_found = len(revealed_tiles)

    # Calculate Math
    current_multiplier = Decimal(str(MULTIPLIERS[gems_found - 1]))
    current_payout = bet_amount * current_multiplier

    #---2.5 CASHOUT STATE ----


    # --- 3. WIN CASE ---
    mines_count = len(mine_locations)
    if len(revealed_tiles) == (9 - mines_count):
        request.session['game_active'] = False

        # Pull the LOCKED bet amount from the session
        bet_amount_str = request.session.get('active_bet', '0')
        bet_amount = Decimal(bet_amount_str)

        # select_for_update() locks the row — reveal_tile already has
        # @transaction.atomic so the lock holds until the response is sent.
        user = User.objects.select_for_update().get(pk=request.user.pk)

        multiplier = Decimal(str(MULTIPLIERS[5]))

        payout = bet_amount * multiplier

        user.usdt_balance += payout
        user.save()

        # Clear the active bet so it can't be reused
        request.session['active_bet'] = '0'

        # Render the win popup
        response = render(request, 'mines/partials/win_screen.html', {
            'new_balance': user.usdt_balance,
            'payout' : payout
        })

        # OOB: Update balance and reset button
        win_ui = f'''
        <span id="user-balance" hx-swap-oob="true" class="text-white font-mono font-bold">
            {user.usdt_balance:.2f}
        </span>
        <div id="button-container" hx-swap-oob="true">
            <button hx-post="/start-game/" hx-include="#bet_amount" hx-target="#game-grid"
                    class="w-full mt-6 py-4 bg-orange-500 text-black font-black rounded-xl uppercase">
                Play
            </button>
            <!-- Play sound after modal is loaded -->
            <script>
                const sound = document.getElementById('sound-win');
                if (sound) {{
                    sound.currentTime = 0;
                    sound.play().catch(err => console.log('Audio play failed:', err));
                }}
            </script>
        </div>
        '''

        response.content += win_ui.encode('utf-8')
        return response

    # Just a regular gem reveal
    response = render(request, 'mines/partials/gem.html')

    next_multiplier = MULTIPLIERS[gems_found] if gems_found < 6 else 0
    nextprofit =  float(bet_amount) * next_multiplier

    oob_updates = f'''
        <div id="cashout-display" hx-swap-oob="true" class="w-full lg:w-auto py-1 lg:py-3 text-center">
            <div class="flex justify-around items-center bg-slate-900/50 border border-slate-800 rounded-2xl p-2 lg:p-3 mx-4 lg:mx-0">
                <div class="flex flex-col">
                    <span class="text-[10px] text-slate-500 font-bold uppercase">Profit</span>
                    <span class="text-lg font-black text-white">{current_payout:.2f} <span class="text-[10px] text-orange-500">PKR</span></span>
                </div>
                <div class="flex flex-col">
                    <span class="text-[10px] text-slate-500 font-bold uppercase">Next Tile profit</span>
                    <span class="text-lg font-black text-orange-500">{nextprofit} <span class="text-[10px] text-white">PKR</span></span>
                </div>
            </div>
        </div>
        <div id="button-container" hx-swap-oob="true" class="mt-3 lg:mt-6">
            <button hx-post="/cashout/" 
                    class="w-full py-3 lg:py-4 bg-orange-500 hover:bg-orange-400 text-black font-black rounded-xl transition-all active:translate-y-1 uppercase">
                Cashout {current_payout:.2f}
            </button>
        </div>
    '''
    response.content += oob_updates.encode('utf-8')
    return response

from django.utils.encoding import force_bytes


@require_POST
def reset_game(request):
    # 1. Check if logged in
    if not request.user.is_authenticated:
        return HttpResponse("Unauthorized", status=401)

    # 2. Check if verified
    #if not request.user.is_verified:
    #    return HttpResponse("Verification Required", status=403)


    try:
        # 1. Clear game state
        request.session['mine_locations'] = []
        request.session['revealed_tiles'] = []
        request.session['game_active'] = False

        # Clear database control field
        request.user.active_mine_coords = ""
        request.user.save()

        # 2. Get the base response (The Blank Grid)
        response = render(request, 'mines/partials/grid.html', {
            'range': range(9),
            'idle': True
        })

        # 3. Define OOB Swaps as strings first
        # IMPORTANT: No spaces inside hx-swap-oob="true"
        clear_overlay = b'<div id="game-overlay" hx-swap-oob="true"></div>'

        button_reset = f'''
                <div id="button-container" hx-swap-oob="true">
                    <button hx-post="/start-game/" hx-include="#bet_amount" hx-target="#game-grid"
                            class="w-full mt-6 py-4 bg-orange-500 hover:bg-orange-400 text-black font-black rounded-xl transition-all shadow-[0_4px_0_rgb(194,120,3)] active:translate-y-1 uppercase">
                        Play
                    </button>
                </div>
                <div id="cashout-display" hx-swap-oob="true" class="lg:hidden">
                    <div class="text-slate-600 text-xs font-bold uppercase tracking-[0.2em] text-center py-2">
                        Ready to play
                    </div>
                </div>
                <div id="game-overlay" hx-swap-oob="true"></div>
                '''

        # 4. Append them as BYTES to the existing response content
        response.content += force_bytes(clear_overlay)
        response.content += force_bytes(button_reset)

        return response

    except Exception as e:
        print(f"Error in reset_game: {e}")
        return HttpResponse("Internal Server Error", status=500)



def logout_user(request):
    logout(request)

    # Check if the request came from HTMX
    if request.headers.get('HX-Request'):
        response = HttpResponse()
        # This is the "Magic" header that forces a full page reload
        response['HX-Redirect'] = '/'
        return response

    return redirect('home')  # Fallback for normal links


from django.contrib.auth.decorators import login_required


@login_required
def wallet_modal(request):
    # Make sure this returns the wallet_modal.html template
    return render(request, 'mines/partials/wallet_modal.html', {
        'user': request.user
    })


@login_required
@require_POST
def submit_withdrawal(request):
    address = request.POST.get('withdrawID')

    if not address or len(address) < 10:
        return HttpResponse('<p class="text-red-500 text-xs mb-4">Please enter a valid address.</p>')

    # Update the backend
    user = request.user
    user.withdrawal_address = address
    user.save()

    return HttpResponse('<p class="text-emerald-500 text-xs mb-4">Withdrawal request saved!</p>')


@login_required
def upload_receipt(request):
    if request.method == 'POST' and request.FILES.get('deposit_receipt'):
        user = request.user
        user.deposit_receipt = request.FILES['deposit_receipt']
        user.save()

        # We return a small snippet to show the user the upload worked
        return HttpResponse(f'''
            <div class="bg-slate-800 p-2 rounded-lg">
                <svg class="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                </svg>
            </div>
            <span class="text-[10px] text-green-500 font-medium truncate">Upload Successful!</span>
        ''')
    return HttpResponse("Upload Failed", status=400)









'''
@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.method == 'GET':
        # Show the login modal
        return render(request, 'mines/partials/login_modal.html')

    # Handle POST request
    un = request.POST.get('username')
    ps = request.POST.get('password')

    # Validate inputs
    if not un or not ps:
        return HttpResponse(
            '<span class="text-red-500 text-xs font-bold uppercase">Username and password required</span>'
        )

    # Check if user exists
    user_exists = User.objects.filter(username=un).exists()

    if user_exists:
        # Existing user - authenticate
        user = authenticate(request, username=un, password=ps)

        if user is None:
            # Wrong password
            return HttpResponse(
                '<span class="text-red-500 text-xs font-bold uppercase">Incorrect password</span>'
            )

        # Login successful
        login(request, user)

        # Reload the page to update navbar and show wallet if needed
        return HttpResponse(
            '<script>window.location.reload();</script>'
        )

    else:
        # New user - instant signup
        user = User.objects.create_user(username=un, password=ps)
        login(request, user)

        # Reload the page - wallet modal will show automatically via board.html
        return HttpResponse(
            '<script>window.location.reload();</script>'
        )

'''

'''
                # Determine which content to show
                if not user.phone_number or not user.cnic_number:
                    response = render(request, 'mines/partials/kyc_form.html')
                elif not user.is_verified:
                    response = render(request, 'mines/partials/kyc_pending.html')
                else:
                    return HttpResponse('<script>window.location.reload();</script>')

                # THE FIX: Tell HTMX to replace the WHOLE overlay, not just the error div
                response['HX-Retarget'] = '#game-overlay'
                return response

            # Failure case: Target remains #auth-error (as defined in HTML)
            return HttpResponse('<span class="text-red-500 text-xs">Invalid Credentials</span>')

        return render(request, 'mines/partials/login_modal.html')
'''