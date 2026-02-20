/*! jQuery Slim (Custom Micro-Implementation for Cagri Vakti) | (c) 2024 Yiğit Gülyurt | MIT License */
(function() {
    'use strict';

    // Core Constructor
    var $ = function(selector) {
        return new Init(selector);
    };

    // Internal Class
    class Init {
        constructor(selector) {
            this.length = 0;
            if (!selector) return;

            // Handle $(function) -> Ready
            if (typeof selector === 'function') {
                if (document.readyState !== 'loading') selector();
                else document.addEventListener('DOMContentLoaded', selector);
                return;
            }

            // Handle $(DOMElement) / $(window)
            if (selector instanceof HTMLElement || selector === window || selector === document) {
                this[0] = selector;
                this.length = 1;
                return;
            }

            // Handle HTML string $('<tag>')
            if (typeof selector === 'string' && selector.trim().startsWith('<')) {
                var div = document.createElement('div');
                div.innerHTML = selector;
                var children = Array.from(div.children);
                children.forEach((el, i) => this[i] = el);
                this.length = children.length;
                return;
            }

            // Handle CSS Selector
            if (typeof selector === 'string') {
                var els = document.querySelectorAll(selector);
                els.forEach((el, i) => this[i] = el);
                this.length = els.length;
                return;
            }
            
            // Handle $(jQueryObject)
            if (selector instanceof Init) {
                return selector;
            }
        }

        each(fn) {
            for (let i = 0; i < this.length; i++) {
                fn.call(this[i], i, this[i]);
            }
            return this;
        }

        ready(fn) {
            if (document.readyState !== 'loading') fn();
            else document.addEventListener('DOMContentLoaded', fn);
            return this;
        }

        on(event, handler) {
            return this.each(function() {
                this.addEventListener(event, handler);
            });
        }

        click(handler) {
            return this.on('click', handler);
        }

        // Classes
        addClass(cls) {
            return this.each(function() {
                if(cls) this.classList.add(...cls.split(' ').filter(Boolean));
            });
        }

        removeClass(cls) {
            return this.each(function() {
                if(cls) this.classList.remove(...cls.split(' ').filter(Boolean));
            });
        }

        hasClass(cls) {
            return this[0] ? this[0].classList.contains(cls) : false;
        }

        // Visibility
        toggle(state) {
            return this.each(function() {
                var show = typeof state === 'boolean' ? state : (getComputedStyle(this).display === 'none');
                this.style.display = show ? '' : 'none';
            });
        }
        show() { return this.toggle(true); }
        hide() { return this.toggle(false); }

        // Content
        text(val) {
            if (val === undefined) return this[0] ? this[0].textContent : '';
            return this.each(function() { this.textContent = val; });
        }

        html(val) {
            if (val === undefined) return this[0] ? this[0].innerHTML : '';
            return this.each(function() { this.innerHTML = val; });
        }

        val(v) {
            if (v === undefined) return this[0] ? this[0].value : '';
            return this.each(function() { this.value = v; });
        }

        empty() {
            return this.each(function() { this.innerHTML = ''; });
        }

        // Attributes & Data
        attr(name, val) {
            if (val === undefined) return this[0]?.getAttribute(name);
            return this.each(function() { this.setAttribute(name, val); });
        }

        data(key, val) {
            if (val === undefined) return this[0]?.dataset[key];
            return this.each(function() { this.dataset[key] = val; });
        }

        css(obj) {
            return this.each(function() {
                for (var key in obj) {
                    this.style[key] = obj[key];
                }
            });
        }

        // Traversal & Manipulation
        find(selector) {
            var found = [];
            var isVisibleCheck = selector.endsWith(':visible');
            var realSelector = isVisibleCheck ? selector.replace(':visible', '') : selector;
            
            this.each(function() {
                var els = this.querySelectorAll(realSelector);
                els.forEach(el => {
                    if (isVisibleCheck) {
                        if (el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0) {
                            found.push(el);
                        }
                    } else {
                        found.push(el);
                    }
                });
            });
            // Unique & Return
            found = [...new Set(found)];
            var ret = new Init();
            found.forEach((el, i) => ret[i] = el);
            ret.length = found.length;
            return ret;
        }

        next(selector) {
             var found = [];
             this.each(function() {
                 var n = this.nextElementSibling;
                 if (n && (!selector || n.matches(selector))) found.push(n);
             });
             var ret = new Init();
             found.forEach((el, i) => ret[i] = el);
             ret.length = found.length;
             return ret;
        }

        append(content) {
            return this.each(function() {
                if (typeof content === 'string') {
                    this.insertAdjacentHTML('beforeend', content);
                } else if (content instanceof Init) {
                    content.each(child => this.appendChild(child));
                } else if (content instanceof HTMLElement) {
                    this.appendChild(content);
                }
            });
        }
    }

    // AJAX Shim (Fetch-based)
    $.get = function(u) {
        var p = fetch(u).then(function(r){
            if(!r.ok) throw new Error(r.statusText);
            return r.json();
        });
        return {
            done: function(c){ p.then(c); return this; },
            fail: function(c){ p.catch(c); return this; },
            always: function(c){ p.finally(c); return this; }
        };
    };
    $.ajax = function(o){ if(o&&o.url) return $.get(o.url); };

    // Expose
    window.jQuery = window.$ = $;

})();