/**
 * InAppRedirect.js - Modern In-App Browser Detection & Redirection Library
 * 
 * Version: 1.0.0
 * Author: Code Assistant
 * Purpose: Detects in-app browsers (Instagram, Facebook, TikTok, etc.) 
 * and encourages users to switch to an external browser for better PWA support.
 */

class InAppRedirect {
    constructor(options = {}) {
        // Configuration
        this.config = {
            appName: 'Çağrı Vakti',
            localStorageKey: 'inapp_banner_dismissed',
            bannerClass: 'in-app-banner',
            primaryColor: '#FFC107',
            darkMode: true,
            androidIntent: true,
            iosSafariTip: true,
            onDetect: null,
            onAction: null,
            onDismiss: null,
            ...options
        };

        this.ua = navigator.userAgent || navigator.vendor || window.opera;
        this.isInApp = this._checkInApp();
        this.isBot = /bot|googlebot|crawler|spider|robot|crawling/i.test(this.ua);
        
        // Initialize if not a bot and in-app browser detected
        if (this.isInApp && !this.isBot) {
            this._init();
        }
    }

    /**
     * Detect common in-app browsers using Regex
     */
    _checkInApp() {
        const rules = [
            'FBAN', 'FBAV', // Facebook
            'Instagram',    // Instagram
            'TikTok',       // TikTok
            'Telegram',     // Telegram
            'Snapchat',     // Snapchat
            'Line',         // Line
            'Musical-ly',   // TikTok legacy
            'WhatsApp',     // WhatsApp
            'FBIOS', 'FB_IAB', // FB iOS
            'FB4A',         // FB Android
            'Twitter',      // Twitter
            'Pinterest',    // Pinterest
            'MicroMessenger' // WeChat
        ];
        const regex = new RegExp('(' + rules.join('|') + ')', 'i');
        return regex.test(this.ua);
    }

    _init() {
        // Check if user previously dismissed the banner
        if (localStorage.getItem(this.config.localStorageKey)) return;

        // Lazy initialize UI
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this._render());
        } else {
            this._render();
        }

        // Trigger detection event
        this._triggerEvent('onDetect', { ua: this.ua });
    }

    _render() {
        this._injectStyles();
        
        const banner = document.createElement('div');
        banner.id = 'in-app-redirect-banner';
        banner.className = `pwa-install-banner active ${this.config.darkMode ? 'dark-mode' : ''}`;
        
        const isIOS = /iPad|iPhone|iPod/.test(this.ua) && !window.MSStream;
        const isAndroid = /Android/.test(this.ua);

        banner.innerHTML = `
            <div class="pwa-content">
                <div class="pwa-icon">
                    <div class="pwa-icon-bg">
                        <span class="pwa-rocket">🚀</span>
                    </div>
                </div>
                <div class="pwa-text">
                    <h3>${this.config.appName}</h3>
                    <p>Instagram içi tarayıcı yerine gerçek tarayıcıda daha hızlı ve stabil deneyim.</p>
                </div>
            </div>
            
            <div class="pwa-actions">
                <button id="iar-action-btn" class="btn btn-primary btn-sm">
                    <span class="btn-text">Tarayıcıda Aç</span>
                </button>
                <button id="iar-close-btn" class="btn-close-pwa">
                    <svg class="icon" aria-hidden="true" style="width:16px;height:16px;">
                        <use xlink:href="#fa-xmark"></use>
                    </svg>
                </button>
            </div>
            
            ${isIOS && this.config.iosSafariTip ? `
                <div class="ios-tip-overlay">
                    <div class="ios-tip-box">
                        <span class="ios-tip-icon">💡</span>
                        <span>
                            Sağ alttaki <b>Paylaş</b> ikonuna basıp <b>Safari'de Aç</b> seçeneğini seçin.
                        </span>
                    </div>
                </div>
            ` : ''}
        `;

        document.body.appendChild(banner);

        // Event Listeners
        document.getElementById('iar-action-btn').addEventListener('click', () => this._handleAction(isAndroid));
        document.getElementById('iar-close-btn').addEventListener('click', () => this._handleDismiss());
        
        this._triggerEvent('onShow');
    }

    _handleAction(isAndroid) {
        this._triggerEvent('onAction');

        if (isAndroid && this.config.androidIntent) {
            const url = window.location.href.replace(/https?:\/\//, '');
            const intentUrl = `intent://${url}#Intent;scheme=https;package=com.android.chrome;end`;
            window.location.replace(intentUrl);
        } else {
            // Fallback: Copy URL or show instructions
            const tempInput = document.createElement('input');
            tempInput.value = window.location.href;
            document.body.appendChild(tempInput);
            tempInput.select();
            document.execCommand('copy');
            document.body.removeChild(tempInput);
            alert('Bağlantı kopyalandı! Lütfen tarayıcınıza yapıştırın.');
        }
    }

    _handleDismiss() {
        localStorage.setItem(this.config.localStorageKey, 'true');
        const banner = document.getElementById('in-app-redirect-banner');
        if (banner) {
            banner.classList.remove('active');
            setTimeout(() => banner.remove(), 500);
        }
        this._triggerEvent('onDismiss');
    }

    _injectStyles() {
        if (document.getElementById('iar-styles')) return;

        const styles = `
                .pwa-icon-bg {
                    width: 48px;
                    height: 48px;
                    border-radius: 14px;
                    background: linear-gradient(135deg, var(--primary), rgba(255,193,7,0.6));
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    box-shadow: 0 6px 20px rgba(255,193,7,0.35);
                }
                    
                .pwa-rocket {
                    font-size: 22px;
                    transform: translateY(-1px);
                }
                    
                #in-app-redirect-banner {
                    backdrop-filter: blur(14px);
                    background: rgba(20, 20, 20, 0.85);
                    border: 1px solid rgba(255, 193, 7, 0.25);
                }
                    
                .btn-primary {
                    transition: all 0.25s ease;
                }
                    
                .btn-primary:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 8px 20px rgba(255,193,7,0.4);
                }
                    
                .btn-primary:active {
                    transform: scale(0.97);
                }
                    
                .btn-close-pwa:hover {
                    opacity: 0.7;
                    transform: rotate(90deg);
                    transition: 0.25s ease;
                }
                    
                .ios-tip-box {
                    display: flex;
                    align-items: flex-start;
                    gap: 8px;
                    background: rgba(255,255,255,0.04);
                    padding: 8px 10px;
                    border-radius: 8px;
                }
                    
                .ios-tip-icon {
                    font-size: 14px;
                    margin-top: 1px;
                }
        `;

        const styleSheet = document.createElement('style');
        styleSheet.id = 'iar-styles';
        styleSheet.textContent = styles;
        document.head.appendChild(styleSheet);
    }

    _triggerEvent(name, data = {}) {
        if (typeof this.config[name] === 'function') {
            this.config[name](data);
        }
        
        // Custom DOM Event
        const event = new CustomEvent(`InAppRedirect:${name}`, { detail: data });
        document.dispatchEvent(event);
    }
}

// Export for different environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = InAppRedirect;
} else {
    window.InAppRedirect = InAppRedirect;
}
