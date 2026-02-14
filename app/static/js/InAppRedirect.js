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
                    <span style="font-size: 32px;">🚀</span>
                </div>
                <div class="pwa-text">
                    <h3>${this.config.appName}</h3>
                    <p>Daha iyi deneyim için tarayıcıda açın.</p>
                </div>
            </div>
            <div class="pwa-actions">
                <button id="iar-action-btn" class="btn btn-primary btn-sm">Aç</button>
                <button id="iar-close-btn" class="btn-close-pwa">
                    <svg class="icon" aria-hidden="true" style="width:14px;height:14px;"><use xlink:href="#fa-xmark"></use></svg>
                </button>
            </div>
            ${isIOS && this.config.iosSafariTip ? `
                <div class="ios-tip-overlay">
                    <span>💡 Safari'de açmak için sağ alttaki <b>Paylaş</b> ikonuna basıp <b>Safari'de Aç</b> seçeneğini seçin.</span>
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
            #in-app-redirect-banner {
                position: fixed;
                bottom: 20px;
                left: 20px;
                right: 20px;
                background: var(--card-bg);
                border: 1px solid rgba(255, 193, 7, 0.2);
                border-radius: 16px;
                padding: 16px;
                display: flex;
                flex-direction: column;
                z-index: 10001;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
                transform: translateY(150%);
                transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
                max-width: 500px;
                margin: 0 auto;
            }

            #in-app-redirect-banner.active {
                transform: translateY(0);
            }

            .pwa-content {
                display: flex;
                align-items: center;
                gap: 12px;
                width: 100%;
                justify-content: space-between;
                margin-bottom: 0;
            }

            #in-app-redirect-banner .pwa-content {
                justify-content: flex-start;
            }

            .pwa-icon {
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .pwa-text h3 {
                font-size: 1rem;
                margin: 0;
                color: var(--text);
                font-weight: 700;
            }

            .pwa-text p {
                font-size: 0.85rem;
                color: var(--gray);
                margin: 0;
            }

            .pwa-actions {
                position: absolute;
                right: 16px;
                top: 50%;
                transform: translateY(-50%);
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .btn-primary {
                background: var(--primary);
                color: #000 !important;
                border: none;
                padding: 8px 16px;
                border-radius: 8px;
                font-size: 0.9rem;
                font-weight: 600;
                cursor: pointer;
            }

            .btn-close-pwa {
                background: transparent;
                border: none;
                color: var(--gray);
                cursor: pointer;
                padding: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .ios-tip-overlay {
                margin-top: 12px;
                padding-top: 12px;
                border-top: 1px solid rgba(255, 255, 255, 0.05);
                font-size: 11px;
                color: var(--gray);
                line-height: 1.4;
            }

            @media (max-width: 480px) {
                #in-app-redirect-banner {
                    bottom: 10px;
                    left: 10px;
                    right: 10px;
                    padding: 12px;
                }
                .pwa-text p {
                    display: none;
                }
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
