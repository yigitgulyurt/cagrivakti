/**
 * jQuery-CagriVakti (Micro-jQuery)
 * A lightweight, custom implementation of jQuery methods used in Cagri Vakti project.
 * Reduces file size from ~87KB to ~4KB.
 */
(function() {
    'use strict';

    function $(selector) {
        // $(function) -> Ready handler
        if (typeof selector === 'function') {
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', selector);
            } else {
                selector();
            }
            return;
        }
        
        // $(DOMElement)
        if (selector instanceof HTMLElement || selector === window || selector === document) {
            return new JQ([selector]);
        }
        
        // $(selector) or $('<tag>')
        if (typeof selector === 'string') {
            if (selector.startsWith('<')) {
                // Create element: $('<a>')
                const tagName = selector.replace(/[<>]/g, '');
                return new JQ([document.createElement(tagName)]);
            }
            // Select elements
            return new JQ(document.querySelectorAll(selector));
        }
        
        return new JQ([]);
    }

    class JQ {
        constructor(elements) {
            this.elements = elements instanceof NodeList ? Array.from(elements) : (Array.isArray(elements) ? elements : [elements]);
            this.length = this.elements.length;
        }

        each(callback) {
            this.elements.forEach((el, index) => callback.call(el, index, el));
            return this;
        }

        on(event, callback) {
            return this.each((i, el) => {
                el.addEventListener(event, function(e) {
                    callback.call(el, e);
                });
            });
        }
        
        click(callback) {
            return this.on('click', callback);
        }

        addClass(className) {
            return this.each((i, el) => {
                if (className) el.classList.add(...className.split(' ').filter(c => c));
            });
        }

        removeClass(className) {
             return this.each((i, el) => {
                if (className) el.classList.remove(...className.split(' ').filter(c => c));
             });
        }
        
        hasClass(className) {
            return this.elements.some(el => el.classList.contains(className));
        }

        attr(name, value) {
            if (value === undefined) return this.elements[0]?.getAttribute(name);
            return this.each((i, el) => el.setAttribute(name, value));
        }

        data(name) {
             return this.elements[0]?.dataset[name];
        }

        val(value) {
            if (value === undefined) return this.elements[0]?.value;
            return this.each((i, el) => el.value = value);
        }

        text(text) {
             if (text === undefined) return this.elements[0]?.textContent;
             return this.each((i, el) => el.textContent = text);
        }
        
        html(html) {
             if (html === undefined) return this.elements[0]?.innerHTML;
             return this.each((i, el) => el.innerHTML = html);
        }

        css(prop, value) {
             if (typeof prop === 'object') {
                 return this.each((i, el) => Object.assign(el.style, prop));
             }
             return this.each((i, el) => el.style[prop] = value);
        }

        show() {
             return this.each((i, el) => el.style.display = '');
        }
        
        hide() {
             return this.each((i, el) => el.style.display = 'none');
        }

        toggle(state) {
            return this.each((i, el) => {
                const isHidden = window.getComputedStyle(el).display === 'none';
                const shouldShow = state !== undefined ? state : isHidden;
                el.style.display = shouldShow ? '' : 'none';
            });
        }

        append(child) {
             return this.each((i, el) => {
                 if (child instanceof JQ) {
                     child.elements.forEach(c => el.appendChild(c));
                 } else if (child instanceof Node) {
                     el.appendChild(child);
                 }
             });
        }

        empty() {
             return this.each((i, el) => el.innerHTML = '');
        }

        find(selector) {
            const found = [];
            this.each((i, el) => {
                if (selector.includes(':visible')) {
                    // Custom handling for :visible psuedo-selector
                    const cleanSelector = selector.replace(':visible', '');
                    const nodes = cleanSelector ? el.querySelectorAll(cleanSelector) : el.children;
                    Array.from(nodes).forEach(node => {
                        // Check if element occupies space
                        if (node.offsetWidth > 0 || node.offsetHeight > 0 || node.getClientRects().length > 0) {
                            found.push(node);
                        }
                    });
                } else {
                    found.push(...el.querySelectorAll(selector));
                }
            });
            return new JQ(found);
        }
        
        next(selector) {
             const nextEls = [];
             this.each((i, el) => {
                 let next = el.nextElementSibling;
                 if (selector) {
                     if (next && next.matches(selector)) nextEls.push(next);
                 } else if (next) {
                     nextEls.push(next);
                 }
             });
             return new JQ(nextEls);
        }
    }

    // AJAX Shim using Fetch API
    const createPromiseWrapper = (fetchPromise) => {
        const wrapper = {
            done: (cb) => {
                fetchPromise.then(cb);
                return wrapper;
            },
            fail: (cb) => {
                fetchPromise.catch(cb);
                return wrapper;
            },
            always: (cb) => {
                fetchPromise.finally(cb);
                return wrapper;
            }
        };
        return wrapper;
    };

    $.get = function(url) {
         return createPromiseWrapper(
             fetch(url).then(r => {
                 if (!r.ok) throw new Error(r.statusText);
                 return r.json();
             })
         );
    };
    
    // Alias $.ajax to $.get for simple GET requests found in code
    $.ajax = function(options) {
        if (options && options.url) return $.get(options.url);
    };

    // Expose to window
    window.jQuery = window.$ = $;

})();
