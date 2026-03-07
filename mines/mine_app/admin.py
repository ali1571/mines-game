from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, Q
from .models import User
from django.utils.safestring import mark_safe
from .models import GameLog


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # What shows up in the main list of users
    list_display = ('username', 'usdt_balance', 'is_verified', 'total_games_display', 'win_rate_display', 'net_profit_display', 'cnic_front_preview', 'active_mine_coords', 'deposit_receipt_preview')
    list_editable = ('usdt_balance', 'is_verified')

    # What shows up when you click into a specific user
    readonly_fields = ('active_mine_coords','cnic_front_preview', 'cnic_back_preview', "withdrawal_address", 'deposit_receipt_preview', 'game_statistics_display', )
    fields = ('username', 'first_name', 'last_name', 'usdt_balance', 'is_verified',
              'cnic_number', 'phone_number', 'cnic_front', 'cnic_front_preview',
              'cnic_back', 'cnic_back_preview', 'active_mine_coords', "withdrawal_address",  'deposit_receipt_preview', 'game_statistics_display',)

    def cnic_front_preview(self, obj):
        if obj.cnic_front:
            return format_html('<img src="{}" style="width: 200px; height: auto; border: 2px solid #ccc;" />',
                               obj.cnic_front.url)
        return "No Image Uploaded"

    def cnic_back_preview(self, obj):
        if obj.cnic_back:
            return format_html('<img src="{}" style="width: 200px; height: auto; border: 2px solid #ccc;" />',
                               obj.cnic_back.url)
        return "No Image Uploaded"

    cnic_front_preview.short_description = "CNIC Front View"
    cnic_back_preview.short_description = "CNIC Back View"

    def deposit_receipt_preview(self, obj):
        if obj.deposit_receipt:
            return format_html(
                '<div style="border: 2px solid #ea580c; border-radius: 8px; overflow: hidden; width: 200px;">'
                '<img src="{}" style="width: 100%; height: auto; display: block;" />'
                '</div>',
                obj.deposit_receipt.url
            )
        return "No Receipt Uploaded"

    deposit_receipt_preview.short_description = "Proof of Deposit"

    def get_queryset(self, request):
        # Annotate every user with their stats in a single SQL query
        # instead of hitting the DB once per user per column.
        qs = super().get_queryset(request)
        return qs.annotate(
            _total_games=Count('game_logs'),
            _wins=Count('game_logs', filter=Q(game_logs__outcome='win')),
            _total_wagered=Sum('game_logs__bet_amount'),
            _total_payout=Sum('game_logs__payout_amount'),
        )

    # Custom methods for list display
    def total_games_display(self, obj):
        return obj._total_games

    total_games_display.short_description = 'Games'
    total_games_display.admin_order_field = '_total_games'

    def win_rate_display(self, obj):
        total = obj._total_games
        win_rate = (obj._wins / total * 100) if total else 0

        if win_rate >= 50:
            color = '#10b981'
        elif win_rate >= 30:
            color = '#f59e0b'
        else:
            color = '#ef4444'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color,
            round(win_rate, 1)
        )

    win_rate_display.short_description = 'Win Rate'

    def net_profit_display(self, obj):
        wagered = obj._total_wagered or 0
        payout = obj._total_payout or 0
        net_profit = payout - wagered

        color = '#10b981' if net_profit <= 0 else '#ef4444'
        symbol = '-' if net_profit < 0 else '+'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{} Rs {}</span>',
            color,
            symbol,
            round(abs(net_profit), 2)
        )

    net_profit_display.short_description = 'Player P/L'

    # Detailed stats for detail view
    def game_statistics_display(self, obj):
        """Show comprehensive game statistics in detail view"""
        stats = obj.get_game_stats()

        # Format numbers first
        win_rate = round(stats['win_rate'], 1)
        total_wagered = round(stats['total_wagered'], 2)
        total_payout = round(stats['total_payout'], 2)
        net_profit = round(stats['net_profit'], 2)
        house_profit = round(-stats['net_profit'], 2)

        # Determine colors and symbols
        profit_color = '#ef4444' if net_profit > 0 else '#10b981'
        profit_symbol = '−' if net_profit < 0 else '+'
        profit_text = 'Player is down' if net_profit < 0 else 'Player is up'

        html = f"""
        <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 10px 0;">
            <h3 style="margin-top: 0; color: #1f2937;">Game Statistics</h3>

            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                <div style="background: white; padding: 15px; border-radius: 6px;">
                    <div style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Total Games</div>
                    <div style="font-size: 24px; font-weight: bold; color: #1f2937;">{stats['total_games']}</div>
                </div>

                <div style="background: white; padding: 15px; border-radius: 6px;">
                    <div style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Win Rate</div>
                    <div style="font-size: 24px; font-weight: bold; color: #10b981;">{win_rate}%</div>
                    <div style="color: #6b7280; font-size: 11px; margin-top: 5px;">
                        {stats['wins']} wins / {stats['losses']} losses
                    </div>
                </div>

                <div style="background: white; padding: 15px; border-radius: 6px;">
                    <div style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Total Wagered</div>
                    <div style="font-size: 24px; font-weight: bold; color: #1f2937;">Rs {total_wagered}</div>
                </div>

                <div style="background: white; padding: 15px; border-radius: 6px;">
                    <div style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Total cashout</div>
                    <div style="font-size: 24px; font-weight: bold; color: #1f2937;">Rs {total_payout}</div>
                </div>

                <div style="background: white; padding: 15px; border-radius: 6px; grid-column: span 2;">
                    <div style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Player Net Profit/Loss</div>
                    <div style="font-size: 32px; font-weight: bold; color: {profit_color};">
                        {profit_symbol} Rs {abs(net_profit)}
                    </div>
                    <div style="color: #6b7280; font-size: 11px; margin-top: 5px;">
                        {profit_text} overall
                    </div>
                </div>
            </div>

            <div style="margin-top: 15px; padding: 10px; background: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px;">
                <strong>House Profit:</strong> Rs {house_profit}
            </div>
        </div>
        """
        return mark_safe(html)

    game_statistics_display.short_description = 'Game Statistics'



from django.contrib import admin
from django.db.models import Sum, Count, Avg
from .models import GameLog


@admin.register(GameLog)
class GameLogAdmin(admin.ModelAdmin):
    list_display = [
        'game_id_short',
        'user',
        'outcome_badge',
        'bet_amount',
        'payout_amount',
        'profit_loss_colored',
        'gems_found',
        'multiplier',
        'game_start_timestamp',
        'device_type',
    ]

    list_filter = [
        'outcome',
        'device_type',
        'game_start_timestamp',
    ]

    search_fields = [
        'user__username',
        'game_id',
        'ip_address',
    ]

    readonly_fields = [
        'game_id',
        'game_start_timestamp',
        'profit_loss',
        'game_duration',

    ]

    fieldsets = (
        ('Game Info', {
            'fields': ('game_id', 'user', 'outcome')
        }),
        ('Financials', {
            'fields': ('bet_amount', 'payout_amount', 'profit_loss', 'multiplier')
        }),

        ('Game Details', {
            'fields': ('gems_found', 'game_start_timestamp', 'game_end_timestamp', 'game_duration')
        }),
        ('Tracking', {
            'fields': ('ip_address', 'device_type', 'user_agent')
        }),
    )

    def game_id_short(self, obj):
        return str(obj.game_id)[:8]

    game_id_short.short_description = 'Game ID'

    def outcome_badge(self, obj):
        colors = {
            'win': '#10b981',
            'loss': '#ef4444',
            'abandoned': '#6b7280'
        }
        return obj.outcome.upper()

    outcome_badge.short_description = 'Outcome'
    outcome_badge.allow_tags = True

    def profit_loss_colored(self, obj):
        color = '#10b981' if obj.profit_loss > 0 else '#ef4444'
        return obj.profit_loss

    profit_loss_colored.short_description = 'House P/L'
    profit_loss_colored.allow_tags = True

    # Prevent editing logs
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False



