from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # The main game board (Now public/accessible to guests)
    path('', views.home, name='home'),

    # Game actions (Protected by login check inside the view)
    path('start-game/', views.start_game, name='start_game'),
    path('reveal/<int:tile_id>/', views.reveal_tile, name='reveal_tile'),
    path('cashout/', views.cashout, name='cashout'),
    path('reset/', views.reset_game, name='reset_game'),

    path('wallet/', views.wallet_modal, name='wallet_modal'),
    path('withdraw-submit/', views.submit_withdrawal, name='submit_withdrawal'),
    path('wallet/upload-receipt/', views.upload_receipt, name='upload_receipt'),

    # Authentication & Profile

    path('login/', views.login_view, name='login_view'),
    path('check-username/', views.check_username, name='check_username'),
    path('login-submit/', views.login_submit, name='login_submit'),
    path('signup-submit/', views.signup_submit, name='signup_submit'),
    path('logout/', views.logout_user, name='logout'),
    path('submit-kyc/', views.submit_kyc, name='submit_kyc'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)