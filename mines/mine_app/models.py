from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from decimal import Decimal
import uuid
from django.db.models import Sum, Count, Avg, F

class User(AbstractUser):
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)

    usdt_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=15,blank=True, null = True)
    cnic_number = models.CharField(max_length=15,blank=True, null = True)
    cnic_front = models.ImageField(upload_to='kyc/' ,blank=True, null = True)
    cnic_back = models.ImageField(upload_to='kyc/',blank=True, null = True)
    deposit_receipt = models.ImageField(upload_to='kyc/receipts/', blank=True, null=True)
    active_mine_coords = models.CharField(max_length=100, blank=True, null=True)
    withdrawal_address = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.username

    # In your User model (models.py)

    def get_game_stats(self):
        """Calculate user's gaming statistics"""
        logs = self.game_logs.all()

        total_games = logs.count()
        if total_games == 0:
            return {
                'total_games': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'total_wagered': 0,
                'total_payout': 0,
                'net_profit': 0,
                'house_profit': 0,
            }

        wins = logs.filter(outcome='win').count()
        losses = logs.filter(outcome='loss').count()

        total_wagered = logs.aggregate(Sum('bet_amount'))['bet_amount__sum'] or 0
        total_payout = logs.aggregate(Sum('payout_amount'))['payout_amount__sum'] or 0
        house_paid_on_wins_only = logs.filter(outcome='win').aggregate(
            total=Sum(F('payout_amount') - F('bet_amount'))
        )['total'] or 0

        return {
            'total_games': total_games,
            'wins': wins,
            'losses': losses,
            'win_rate': (wins / total_games * 100) if total_games > 0 else 0,
            'total_wagered': total_wagered,
            'total_payout': house_paid_on_wins_only,
            'net_profit': total_payout - total_wagered,  # Negative = player lost money
            'house_profit': total_wagered - total_payout, #negative = house lost money
        }


from django.db import models
from django.conf import settings
from decimal import Decimal
import uuid

from django.db import models
from django.conf import settings
from decimal import Decimal
import uuid


class GameLog(models.Model):
    """
    Stores detailed logs of each game session
    """
    # Game Outcome Choices
    OUTCOME_CHOICES = [
        ('win', 'Win'),  # User cashed out or found all 6 gems
        ('loss', 'Loss'),  # User hit a mine
        ('abandoned', 'Abandoned'),  # User left without finishing
    ]

    DEVICE_CHOICES = [
        ('desktop', 'Desktop'),
        ('mobile', 'Mobile'),
        ('tablet', 'Tablet'),
        ('unknown', 'Unknown'),
    ]

    # ===== BASIC IDENTIFIERS =====
    game_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this game session"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='game_logs',
        help_text="Player who played this game"
    )

    # ===== GAME FINANCIALS =====
    bet_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount wagered in PKR"
    )

    payout_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount paid out to player (0 if lost)"
    )

    profit_loss = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="House profit/loss (bet - payout). Positive = house profit"
    )

    # ===== GAME DETAILS =====
    gems_found = models.IntegerField(
        default=0,
        help_text="Number of gems revealed before cashout/mine"
    )

    outcome = models.CharField(
        max_length=20,
        choices=OUTCOME_CHOICES,
        default='abandoned',
        help_text="Final result of the game"
    )

    multiplier = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Multiplier applied (based on gems found)"
    )

    # ===== TIMESTAMPS =====
    game_start_timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When the game started"
    )

    game_end_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the game ended"
    )

    game_duration = models.IntegerField(
        null=True,
        blank=True,
        help_text="Game duration in seconds"
    )

    # ===== USER TRACKING =====
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the player"
    )

    device_type = models.CharField(
        max_length=20,
        choices=DEVICE_CHOICES,
        default='unknown',
        help_text="Device used to play"
    )

    user_agent = models.TextField(
        blank=True,
        help_text="Full user agent string"
    )

    class Meta:
        ordering = ['-game_start_timestamp']
        verbose_name = "Game Log"
        verbose_name_plural = "Game Logs"
        indexes = [
            models.Index(fields=['-game_start_timestamp']),  # Speed up date queries
            models.Index(fields=['user', '-game_start_timestamp']),  # Speed up user history
            models.Index(fields=['outcome']),  # Speed up win/loss queries
        ]

    def __str__(self):
        return f"Game {str(self.game_id)[:8]} - {self.user.username} - {self.outcome}"

    def calculate_duration(self):
        """Calculate game duration in seconds"""
        if self.game_end_timestamp and self.game_start_timestamp:
            delta = self.game_end_timestamp - self.game_start_timestamp
            return int(delta.total_seconds())
        return None

    def calculate_profit_loss(self):
        """Calculate house profit/loss"""
        return self.bet_amount - self.payout_amount



    def save(self, *args, **kwargs):
        """Override save to auto-calculate fields"""
        # Auto-calculate profit/loss
        if self.payout_amount is not None:
            self.profit_loss = self.calculate_profit_loss()

        # Auto-calculate duration if both timestamps exist
        if self.game_end_timestamp and not self.game_duration:
            self.game_duration = self.calculate_duration()

        super().save(*args, **kwargs)

