"""
Middleware для налаштування CSP заголовків
"""
from django.conf import settings

class CSPMiddleware:
    """Middleware для налаштування Content Security Policy"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Встановлюємо CSP заголовки тільки в режимі розробки
        if settings.DEBUG and hasattr(response, 'headers'):
            # Формуємо CSP політику з налаштувань
            csp_policy = []
            
            if hasattr(settings, 'CSP_DEFAULT_SRC'):
                csp_policy.append(f"default-src {' '.join(settings.CSP_DEFAULT_SRC)}")
            
            if hasattr(settings, 'CSP_SCRIPT_SRC'):
                csp_policy.append(f"script-src {' '.join(settings.CSP_SCRIPT_SRC)}")
            
            if hasattr(settings, 'CSP_STYLE_SRC'):
                csp_policy.append(f"style-src {' '.join(settings.CSP_STYLE_SRC)}")
            
            if hasattr(settings, 'CSP_FONT_SRC'):
                csp_policy.append(f"font-src {' '.join(settings.CSP_FONT_SRC)}")
            
            if hasattr(settings, 'CSP_IMG_SRC'):
                csp_policy.append(f"img-src {' '.join(settings.CSP_IMG_SRC)}")
            
            if hasattr(settings, 'CSP_CONNECT_SRC'):
                csp_policy.append(f"connect-src {' '.join(settings.CSP_CONNECT_SRC)}")
            
            if csp_policy:
                response.headers['Content-Security-Policy'] = '; '.join(csp_policy) + ';'
        
        return response
