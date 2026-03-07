# mine_app/utils.py

def get_client_ip(request):
    """
    Extract the real IP address from request
    Handles proxies and load balancers
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_device_type(request):
    """
    Determine device type from user agent
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()

    # Mobile devices
    mobile_keywords = ['mobile', 'android', 'iphone', 'ipod', 'blackberry', 'windows phone']
    if any(keyword in user_agent for keyword in mobile_keywords):
        return 'mobile'

    # Tablets
    tablet_keywords = ['ipad', 'tablet', 'kindle']
    if any(keyword in user_agent for keyword in tablet_keywords):
        return 'tablet'

    # Desktop
    desktop_keywords = ['windows', 'macintosh', 'linux', 'x11']
    if any(keyword in user_agent for keyword in desktop_keywords):
        return 'desktop'

    return 'unknown'