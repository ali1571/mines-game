from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates the 10 hardcoded game users'

    def handle(self, *args, **kwargs):
        user_credentials = {
            "Maya2847": "kR9#mL2w",
            "Jordan1993": "7Tz$pN4j",
            "Phoenix_426": "Q3v@Hs8x",
            "Ethan.7521": "bF6!dY1m",
            "Luna3604": "W8n%Jk5r",
            "Marcus_88": "5Gp&Xc9t",
            "Sienna1247": "aM4#Lq7z",
            "Kai9536": "9Rw@Vf2n",
            "Violet.302": "Uy6$Hb3k",
            "Felix4782": "3Pt!Ng8s"
        }

        for username, password in user_credentials.items():
            if not User.objects.filter(username=username).exists():
                User.objects.create_user(username=username, password=password)
                self.stdout.write(self.style.SUCCESS(f"Successfully created user: {username}"))
            else:
                self.stdout.write(self.style.WARNING(f"User {username} already exists."))