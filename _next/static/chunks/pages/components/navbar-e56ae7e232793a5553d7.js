(self.webpackChunk_N_E=self.webpackChunk_N_E||[]).push([[437],{2167:function(e,n,t){"use strict";var r=t(3848),o=t(9448);n.default=void 0;var c=o(t(7294)),i=t(9414),a=t(4651),u=t(7426),s={};function l(e,n,t,r){if(e&&(0,i.isLocalURL)(n)){e.prefetch(n,t,r).catch((function(e){0}));var o=r&&"undefined"!==typeof r.locale?r.locale:e&&e.locale;s[n+"%"+t+(o?"%"+o:"")]=!0}}var f=function(e){var n,t=!1!==e.prefetch,o=(0,a.useRouter)(),f=c.default.useMemo((function(){var n=(0,i.resolveHref)(o,e.href,!0),t=r(n,2),c=t[0],a=t[1];return{href:c,as:e.as?(0,i.resolveHref)(o,e.as):a||c}}),[o,e.href,e.as]),d=f.href,h=f.as,p=e.children,v=e.replace,_=e.shallow,m=e.scroll,g=e.locale;"string"===typeof p&&(p=c.default.createElement("a",null,p));var b=(n=c.Children.only(p))&&"object"===typeof n&&n.ref,y=(0,u.useIntersection)({rootMargin:"200px"}),w=r(y,2),x=w[0],T=w[1],E=c.default.useCallback((function(e){x(e),b&&("function"===typeof b?b(e):"object"===typeof b&&(b.current=e))}),[b,x]);(0,c.useEffect)((function(){var e=T&&t&&(0,i.isLocalURL)(d),n="undefined"!==typeof g?g:o&&o.locale,r=s[d+"%"+h+(n?"%"+n:"")];e&&!r&&l(o,d,h,{locale:n})}),[h,d,T,g,t,o]);var H={ref:E,onClick:function(e){n.props&&"function"===typeof n.props.onClick&&n.props.onClick(e),e.defaultPrevented||function(e,n,t,r,o,c,a,u){("A"!==e.currentTarget.nodeName||!function(e){var n=e.currentTarget.target;return n&&"_self"!==n||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.nativeEvent&&2===e.nativeEvent.which}(e)&&(0,i.isLocalURL)(t))&&(e.preventDefault(),null==a&&r.indexOf("#")>=0&&(a=!1),n[o?"replace":"push"](t,r,{shallow:c,locale:u,scroll:a}))}(e,o,d,h,v,_,m,g)},onMouseEnter:function(e){(0,i.isLocalURL)(d)&&(n.props&&"function"===typeof n.props.onMouseEnter&&n.props.onMouseEnter(e),l(o,d,h,{priority:!0}))}};if(e.passHref||"a"===n.type&&!("href"in n.props)){var L="undefined"!==typeof g?g:o&&o.locale,j=o&&o.isLocaleDomain&&(0,i.getDomainLocale)(h,L,o&&o.locales,o&&o.domainLocales);H.href=j||(0,i.addBasePath)((0,i.addLocale)(h,L,o&&o.defaultLocale))}return c.default.cloneElement(n,H)};n.default=f},7426:function(e,n,t){"use strict";var r=t(3848);n.__esModule=!0,n.useIntersection=function(e){var n=e.rootMargin,t=e.disabled||!i,u=(0,o.useRef)(),s=(0,o.useState)(!1),l=r(s,2),f=l[0],d=l[1],h=(0,o.useCallback)((function(e){u.current&&(u.current(),u.current=void 0),t||f||e&&e.tagName&&(u.current=function(e,n,t){var r=function(e){var n=e.rootMargin||"",t=a.get(n);if(t)return t;var r=new Map,o=new IntersectionObserver((function(e){e.forEach((function(e){var n=r.get(e.target),t=e.isIntersecting||e.intersectionRatio>0;n&&t&&n(t)}))}),e);return a.set(n,t={id:n,observer:o,elements:r}),t}(t),o=r.id,c=r.observer,i=r.elements;return i.set(e,n),c.observe(e),function(){i.delete(e),c.unobserve(e),0===i.size&&(c.disconnect(),a.delete(o))}}(e,(function(e){return e&&d(e)}),{rootMargin:n}))}),[t,n,f]);return(0,o.useEffect)((function(){if(!i&&!f){var e=(0,c.requestIdleCallback)((function(){return d(!0)}));return function(){return(0,c.cancelIdleCallback)(e)}}}),[f]),[h,f]};var o=t(7294),c=t(3447),i="undefined"!==typeof IntersectionObserver;var a=new Map},4705:function(e,n,t){"use strict";t.r(n),t.d(n,{default:function(){return l}});var r=t(5893),o=t(3679),c=t.n(o),i=t(5016),a=t.n(i),u=t(1664),s=t(237);function l(){return(0,r.jsxs)("nav",{className:c().nav,children:[(0,r.jsx)("div",{children:(0,r.jsx)(u.default,{href:"/",passHref:!0,children:(0,r.jsx)("a",{id:c().logo,children:(0,r.jsx)(s.default,{src:"/wordmark.svg"})})})}),(0,r.jsxs)("div",{children:[(0,r.jsx)(u.default,{href:"/tutorial",children:(0,r.jsx)("a",{children:"Tutorials"})}),(0,r.jsx)(u.default,{href:"/docs",children:(0,r.jsx)("a",{children:"Docs"})})]}),(0,r.jsx)("div",{children:(0,r.jsx)(u.default,{href:"https://github.com/tfukaza/harvest",children:(0,r.jsx)("a",{className:"".concat(a().button," ").concat(c().github),children:"GitHub"})})})]})}},237:function(e,n,t){"use strict";t.r(n),t.d(n,{default:function(){return i}});var r=t(5893),o=t(4155),c=function(e){var n=o.env.BASE_PATH;return void 0===n&&(n=""),"".concat(n,"/").concat(e)};function i(e){e.props;var n=e.src;return void 0===n?(0,r.jsx)("img",{}):(0,r.jsx)("img",{src:c(n),alt:"img"})}},351:function(e,n,t){(window.__NEXT_P=window.__NEXT_P||[]).push(["/components/navbar",function(){return t(4705)}])},5016:function(e){e.exports={button:"rowcrop_button__1n6eZ",card:"rowcrop_card__25eqx",col4:"rowcrop_col4__2ZQay"}},3679:function(e){e.exports={container:"Home_container__3sao-",main:"Home_main__1Z1aG",nav:"Home_nav__2iapp",logo:"Home_logo__3GqVp",github:"Home_github__3XEl-",landing:"Home_landing__2U_o4",section:"Home_section__354aW",text:"Home_text__dq4ii",button:"Home_button__2hScn",col_card:"Home_col_card__6BIVE",col4:"Home_col4__2OXKu",footer:"Home_footer__2v49s"}},1664:function(e,n,t){e.exports=t(2167)},4155:function(e){var n,t,r=e.exports={};function o(){throw new Error("setTimeout has not been defined")}function c(){throw new Error("clearTimeout has not been defined")}function i(e){if(n===setTimeout)return setTimeout(e,0);if((n===o||!n)&&setTimeout)return n=setTimeout,setTimeout(e,0);try{return n(e,0)}catch(t){try{return n.call(null,e,0)}catch(t){return n.call(this,e,0)}}}!function(){try{n="function"===typeof setTimeout?setTimeout:o}catch(e){n=o}try{t="function"===typeof clearTimeout?clearTimeout:c}catch(e){t=c}}();var a,u=[],s=!1,l=-1;function f(){s&&a&&(s=!1,a.length?u=a.concat(u):l=-1,u.length&&d())}function d(){if(!s){var e=i(f);s=!0;for(var n=u.length;n;){for(a=u,u=[];++l<n;)a&&a[l].run();l=-1,n=u.length}a=null,s=!1,function(e){if(t===clearTimeout)return clearTimeout(e);if((t===c||!t)&&clearTimeout)return t=clearTimeout,clearTimeout(e);try{t(e)}catch(n){try{return t.call(null,e)}catch(n){return t.call(this,e)}}}(e)}}function h(e,n){this.fun=e,this.array=n}function p(){}r.nextTick=function(e){var n=new Array(arguments.length-1);if(arguments.length>1)for(var t=1;t<arguments.length;t++)n[t-1]=arguments[t];u.push(new h(e,n)),1!==u.length||s||i(d)},h.prototype.run=function(){this.fun.apply(null,this.array)},r.title="browser",r.browser=!0,r.env={},r.argv=[],r.version="",r.versions={},r.on=p,r.addListener=p,r.once=p,r.off=p,r.removeListener=p,r.removeAllListeners=p,r.emit=p,r.prependListener=p,r.prependOnceListener=p,r.listeners=function(e){return[]},r.binding=function(e){throw new Error("process.binding is not supported")},r.cwd=function(){return"/"},r.chdir=function(e){throw new Error("process.chdir is not supported")},r.umask=function(){return 0}}},function(e){e.O(0,[774,888,179],(function(){return n=351,e(e.s=n);var n}));var n=e.O();_N_E=n}]);