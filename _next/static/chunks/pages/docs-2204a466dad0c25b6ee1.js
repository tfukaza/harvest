(self.webpackChunk_N_E=self.webpackChunk_N_E||[]).push([[172],{2167:function(e,t,n){"use strict";var r=n(3848),o=n(9448);t.default=void 0;var a=o(n(7294)),i=n(9414),s=n(4651),l=n(7426),u={};function c(e,t,n,r){if(e&&(0,i.isLocalURL)(t)){e.prefetch(t,n,r).catch((function(e){0}));var o=r&&"undefined"!==typeof r.locale?r.locale:e&&e.locale;u[t+"%"+n+(o?"%"+o:"")]=!0}}var d=function(e){var t,n=!1!==e.prefetch,o=(0,s.useRouter)(),d=a.default.useMemo((function(){var t=(0,i.resolveHref)(o,e.href,!0),n=r(t,2),a=n[0],s=n[1];return{href:a,as:e.as?(0,i.resolveHref)(o,e.as):s||a}}),[o,e.href,e.as]),f=d.href,p=d.as,h=e.children,m=e.replace,y=e.shallow,_=e.scroll,v=e.locale;"string"===typeof h&&(h=a.default.createElement("a",null,h));var g=(t=a.Children.only(h))&&"object"===typeof t&&t.ref,b=(0,l.useIntersection)({rootMargin:"200px"}),x=r(b,2),j=x[0],w=x[1],S=a.default.useCallback((function(e){j(e),g&&("function"===typeof g?g(e):"object"===typeof g&&(g.current=e))}),[g,j]);(0,a.useEffect)((function(){var e=w&&n&&(0,i.isLocalURL)(f),t="undefined"!==typeof v?v:o&&o.locale,r=u[f+"%"+p+(t?"%"+t:"")];e&&!r&&c(o,f,p,{locale:t})}),[p,f,w,v,n,o]);var O={ref:S,onClick:function(e){t.props&&"function"===typeof t.props.onClick&&t.props.onClick(e),e.defaultPrevented||function(e,t,n,r,o,a,s,l){("A"!==e.currentTarget.nodeName||!function(e){var t=e.currentTarget.target;return t&&"_self"!==t||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.nativeEvent&&2===e.nativeEvent.which}(e)&&(0,i.isLocalURL)(n))&&(e.preventDefault(),null==s&&r.indexOf("#")>=0&&(s=!1),t[o?"replace":"push"](n,r,{shallow:a,locale:l,scroll:s}))}(e,o,f,p,m,y,_,v)},onMouseEnter:function(e){(0,i.isLocalURL)(f)&&(t.props&&"function"===typeof t.props.onMouseEnter&&t.props.onMouseEnter(e),c(o,f,p,{priority:!0}))}};if(e.passHref||"a"===t.type&&!("href"in t.props)){var k="undefined"!==typeof v?v:o&&o.locale,A=o&&o.isLocaleDomain&&(0,i.getDomainLocale)(p,k,o&&o.locales,o&&o.domainLocales);O.href=A||(0,i.addBasePath)((0,i.addLocale)(p,k,o&&o.defaultLocale))}return a.default.cloneElement(t,O)};t.default=d},7426:function(e,t,n){"use strict";var r=n(3848);t.__esModule=!0,t.useIntersection=function(e){var t=e.rootMargin,n=e.disabled||!i,l=(0,o.useRef)(),u=(0,o.useState)(!1),c=r(u,2),d=c[0],f=c[1],p=(0,o.useCallback)((function(e){l.current&&(l.current(),l.current=void 0),n||d||e&&e.tagName&&(l.current=function(e,t,n){var r=function(e){var t=e.rootMargin||"",n=s.get(t);if(n)return n;var r=new Map,o=new IntersectionObserver((function(e){e.forEach((function(e){var t=r.get(e.target),n=e.isIntersecting||e.intersectionRatio>0;t&&n&&t(n)}))}),e);return s.set(t,n={id:t,observer:o,elements:r}),n}(n),o=r.id,a=r.observer,i=r.elements;return i.set(e,t),a.observe(e),function(){i.delete(e),a.unobserve(e),0===i.size&&(a.disconnect(),s.delete(o))}}(e,(function(e){return e&&f(e)}),{rootMargin:t}))}),[n,t,d]);return(0,o.useEffect)((function(){if(!i&&!d){var e=(0,a.requestIdleCallback)((function(){return f(!0)}));return function(){return(0,a.cancelIdleCallback)(e)}}}),[d]),[p,d]};var o=n(7294),a=n(3447),i="undefined"!==typeof IntersectionObserver;var s=new Map},3398:function(e,t,n){"use strict";var r;t.__esModule=!0,t.AmpStateContext=void 0;var o=((r=n(7294))&&r.__esModule?r:{default:r}).default.createContext({});t.AmpStateContext=o},6393:function(e,t,n){"use strict";t.__esModule=!0,t.isInAmpMode=i,t.useAmp=function(){return i(o.default.useContext(a.AmpStateContext))};var r,o=(r=n(7294))&&r.__esModule?r:{default:r},a=n(3398);function i(){var e=arguments.length>0&&void 0!==arguments[0]?arguments[0]:{},t=e.ampFirst,n=void 0!==t&&t,r=e.hybrid,o=void 0!==r&&r,a=e.hasQuery,i=void 0!==a&&a;return n||o&&i}},2775:function(e,t,n){"use strict";var r=n(1682);function o(e,t){var n=Object.keys(e);if(Object.getOwnPropertySymbols){var r=Object.getOwnPropertySymbols(e);t&&(r=r.filter((function(t){return Object.getOwnPropertyDescriptor(e,t).enumerable}))),n.push.apply(n,r)}return n}t.__esModule=!0,t.defaultHead=f,t.default=void 0;var a,i=function(e){if(e&&e.__esModule)return e;if(null===e||"object"!==typeof e&&"function"!==typeof e)return{default:e};var t=d();if(t&&t.has(e))return t.get(e);var n={},r=Object.defineProperty&&Object.getOwnPropertyDescriptor;for(var o in e)if(Object.prototype.hasOwnProperty.call(e,o)){var a=r?Object.getOwnPropertyDescriptor(e,o):null;a&&(a.get||a.set)?Object.defineProperty(n,o,a):n[o]=e[o]}n.default=e,t&&t.set(e,n);return n}(n(7294)),s=(a=n(3244))&&a.__esModule?a:{default:a},l=n(3398),u=n(1165),c=n(6393);function d(){if("function"!==typeof WeakMap)return null;var e=new WeakMap;return d=function(){return e},e}function f(){var e=arguments.length>0&&void 0!==arguments[0]&&arguments[0],t=[i.default.createElement("meta",{charSet:"utf-8"})];return e||t.push(i.default.createElement("meta",{name:"viewport",content:"width=device-width"})),t}function p(e,t){return"string"===typeof t||"number"===typeof t?e:t.type===i.default.Fragment?e.concat(i.default.Children.toArray(t.props.children).reduce((function(e,t){return"string"===typeof t||"number"===typeof t?e:e.concat(t)}),[])):e.concat(t)}var h=["name","httpEquiv","charSet","itemProp"];function m(e,t){return e.reduce((function(e,t){var n=i.default.Children.toArray(t.props.children);return e.concat(n)}),[]).reduce(p,[]).reverse().concat(f(t.inAmpMode)).filter(function(){var e=new Set,t=new Set,n=new Set,r={};return function(o){var a=!0,i=!1;if(o.key&&"number"!==typeof o.key&&o.key.indexOf("$")>0){i=!0;var s=o.key.slice(o.key.indexOf("$")+1);e.has(s)?a=!1:e.add(s)}switch(o.type){case"title":case"base":t.has(o.type)?a=!1:t.add(o.type);break;case"meta":for(var l=0,u=h.length;l<u;l++){var c=h[l];if(o.props.hasOwnProperty(c))if("charSet"===c)n.has(c)?a=!1:n.add(c);else{var d=o.props[c],f=r[c]||new Set;"name"===c&&i||!f.has(d)?(f.add(d),r[c]=f):a=!1}}}return a}}()).reverse().map((function(e,n){var a=e.key||n;if(!t.inAmpMode&&"link"===e.type&&e.props.href&&["https://fonts.googleapis.com/css","https://use.typekit.net/"].some((function(t){return e.props.href.startsWith(t)}))){var s=function(e){for(var t=1;t<arguments.length;t++){var n=null!=arguments[t]?arguments[t]:{};t%2?o(Object(n),!0).forEach((function(t){r(e,t,n[t])})):Object.getOwnPropertyDescriptors?Object.defineProperties(e,Object.getOwnPropertyDescriptors(n)):o(Object(n)).forEach((function(t){Object.defineProperty(e,t,Object.getOwnPropertyDescriptor(n,t))}))}return e}({},e.props||{});return s["data-href"]=s.href,s.href=void 0,s["data-optimized-fonts"]=!0,i.default.cloneElement(e,s)}return i.default.cloneElement(e,{key:a})}))}var y=function(e){var t=e.children,n=(0,i.useContext)(l.AmpStateContext),r=(0,i.useContext)(u.HeadManagerContext);return i.default.createElement(s.default,{reduceComponentsToState:m,headManager:r,inAmpMode:(0,c.isInAmpMode)(n)},t)};t.default=y},3244:function(e,t,n){"use strict";var r=n(3115),o=n(2553),a=n(2012),i=(n(450),n(9807)),s=n(7690),l=n(9828);function u(e){var t=function(){if("undefined"===typeof Reflect||!Reflect.construct)return!1;if(Reflect.construct.sham)return!1;if("function"===typeof Proxy)return!0;try{return Date.prototype.toString.call(Reflect.construct(Date,[],(function(){}))),!0}catch(e){return!1}}();return function(){var n,r=l(e);if(t){var o=l(this).constructor;n=Reflect.construct(r,arguments,o)}else n=r.apply(this,arguments);return s(this,n)}}t.__esModule=!0,t.default=void 0;var c=n(7294),d=function(e){i(n,e);var t=u(n);function n(e){var a;return o(this,n),(a=t.call(this,e))._hasHeadManager=void 0,a.emitChange=function(){a._hasHeadManager&&a.props.headManager.updateHead(a.props.reduceComponentsToState(r(a.props.headManager.mountedInstances),a.props))},a._hasHeadManager=a.props.headManager&&a.props.headManager.mountedInstances,a}return a(n,[{key:"componentDidMount",value:function(){this._hasHeadManager&&this.props.headManager.mountedInstances.add(this),this.emitChange()}},{key:"componentDidUpdate",value:function(){this.emitChange()}},{key:"componentWillUnmount",value:function(){this._hasHeadManager&&this.props.headManager.mountedInstances.delete(this),this.emitChange()}},{key:"render",value:function(){return null}}]),n}(c.Component);t.default=d},1536:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return a}});var r=n(5893),o=n(7317);function a(e){var t=e.lang,n=e.value;return void 0===t&&(t="text"),void 0===n&&(n="Hello World"),(0,r.jsx)(o.Z,{language:t,customStyle:"",useInlineStyles:!1,children:n})}},2833:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return l}});var r=n(5893),o=n(3679),a=n.n(o),i=n(1664),s=n(237);function l(){return(0,r.jsx)("footer",{className:a().footer,children:(0,r.jsxs)("section",{className:a().section,children:[(0,r.jsxs)("div",{children:[(0,r.jsx)(s.default,{src:"/wordmark.svg"}),(0,r.jsx)(i.default,{href:"https://github.com/tfukaza/harvest/issues/new?assignees=&labels=bug&template=bug_report.md&title=%5B%F0%9F%AA%B0BUG%5D",children:"Report a Bug"}),(0,r.jsx)(i.default,{href:"https://github.com/tfukaza/harvest/issues/new?assignees=&labels=enhancement%2C+question&template=feature-request.md&title=%5B%F0%9F%92%A1Feature+Request%5D",children:"Suggest a Feature"})]}),(0,r.jsxs)("div",{children:[(0,r.jsx)("h3",{children:"Special thanks to these projects:"}),(0,r.jsx)(i.default,{href:"https://github.com/jmfernandes/robin_stocks",children:"robin_stocks"})]})]})})}},3899:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return d}});var r=n(5893),o=n(4139),a=n.n(o),i=n(1536),s=JSON.parse('{"gtc":"Good-Til-Cancelled"}');function l(e,t){var n;if("undefined"===typeof Symbol||null==e[Symbol.iterator]){if(Array.isArray(e)||(n=function(e,t){if(!e)return;if("string"===typeof e)return u(e,t);var n=Object.prototype.toString.call(e).slice(8,-1);"Object"===n&&e.constructor&&(n=e.constructor.name);if("Map"===n||"Set"===n)return Array.from(e);if("Arguments"===n||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n))return u(e,t)}(e))||t&&e&&"number"===typeof e.length){n&&(e=n);var r=0,o=function(){};return{s:o,n:function(){return r>=e.length?{done:!0}:{done:!1,value:e[r++]}},e:function(e){throw e},f:o}}throw new TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.")}var a,i=!0,s=!1;return{s:function(){n=e[Symbol.iterator]()},n:function(){var e=n.next();return i=e.done,e},e:function(e){s=!0,a=e},f:function(){try{i||null==n.return||n.return()}finally{if(s)throw a}}}}function u(e,t){(null==t||t>e.length)&&(t=e.length);for(var n=0,r=new Array(t);n<t;n++)r[n]=e[n];return r}function c(e){return e in s?s[e]:"404"}function d(e){var t=e.dict;if(void 0===t)return(0,r.jsx)("p",{children:":)"});var n=function(e){var t,n=[],o=l(e.params);try{for(o.s();!(t=o.n()).done;){var i=t.value,s=i.desc;void 0===s&&(s="");var u,d=/{[^{}]+}/g,f=s.match(d),p=s.split(d),h=[],m="",y=null,_=l(p);try{for(_.s();!(u=_.n()).done;){var v=u.value;h.push(v),null!==f&&f.length>0&&(m=f.shift().replace(/[{}]/g,""),y=(0,r.jsx)("span",{children:c(m)}),h.push((0,r.jsxs)("span",{className:a().lookup,children:[y,m]})))}}catch(g){_.e(g)}finally{_.f()}n.push((0,r.jsxs)("div",{children:[(0,r.jsxs)("p",{className:a().paramName,children:["\u2022 ",i.name]}),(0,r.jsxs)("p",{className:a().paramType,children:["\xa0(",i.type,"):"]}),(0,r.jsx)("p",{children:h}),(0,r.jsx)("p",{className:a().paramDef,children:i.default}),(0,r.jsx)("p",{children:f})]}))}}catch(g){o.e(g)}finally{o.f()}return n}(t),o=function(e){var t,n=[],o=l(e.raises);try{for(o.s();!(t=o.n()).done;){var a=t.value;n.push((0,r.jsxs)("li",{children:[(0,r.jsx)("span",{children:a.type+": "}),a.desc]}))}}catch(i){o.e(i)}finally{o.f()}return n}(t),s=function(e){var t,n=[],o=e.returns,a=o.match(/(\s*\n\s*- .+)+/g),i=l(o.split(/\s*- [^\n]*/).filter((function(e){return e.length>0})));try{for(i.s();!(t=i.n()).done;){var s=t.value;if(n.push((0,r.jsx)("p",{children:s})),null!==a&&a.length>0){var u,c=a.shift().match(/-.*[^\n]/g),d=[],f=l(c);try{for(f.s();!(u=f.n()).done;){var p=u.value;d.push((0,r.jsx)("li",{children:p.replace(/- /,"")}))}}catch(h){f.e(h)}finally{f.f()}n.push((0,r.jsx)("ul",{children:d}))}}}catch(h){i.e(h)}finally{i.f()}return n}(t);return(0,r.jsxs)("div",{className:a().entry,id:t.index,children:[(0,r.jsx)(i.default,{lang:"python",value:t.function}),(0,r.jsx)("p",{children:t.short_description}),(0,r.jsx)("p",{className:a().longDesc,children:t.long_description}),(0,r.jsxs)("div",{className:a().paramHeader,children:[(0,r.jsx)("h3",{children:"Params:"}),(0,r.jsx)("h4",{children:"Default"}),n]}),(0,r.jsxs)("div",{className:a().paramReturn,children:[(0,r.jsx)("h3",{children:"Returns:"}),s]}),(0,r.jsxs)("div",{className:a().paramRaise,children:[(0,r.jsx)("h3",{children:"Raises:"}),(0,r.jsx)("ul",{className:a().raises,children:o})]})]})}s.returns},6793:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return a}});var r=n(5893),o=n(9008);function a(e){e.c;var t=e.title;return(0,r.jsxs)(o.default,{children:[(0,r.jsx)("title",{children:t}),(0,r.jsx)("meta",{name:"description",content:""}),(0,r.jsx)("meta",{name:"viewport",content:"width=device-width, initial-scale=1.0"}),(0,r.jsx)("meta",{property:"og:title",content:t}),(0,r.jsx)("meta",{property:"og:type",content:"website"}),(0,r.jsx)("meta",{property:"og:image",content:"/img/wordmark.svg"}),(0,r.jsx)("link",{rel:"icon",href:"/favicon.ico"})]})}},4705:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return c}});var r=n(5893),o=n(3679),a=n.n(o),i=n(5016),s=n.n(i),l=n(1664),u=n(237);function c(){return(0,r.jsxs)("nav",{className:a().nav,children:[(0,r.jsx)("div",{children:(0,r.jsx)(l.default,{href:"/",passHref:!0,children:(0,r.jsx)("a",{id:a().logo,children:(0,r.jsx)(u.default,{src:"/wordmark.svg"})})})}),(0,r.jsxs)("div",{children:[(0,r.jsx)(l.default,{href:"/tutorial",children:(0,r.jsx)("a",{children:"Tutorials"})}),(0,r.jsx)(l.default,{href:"/docs",children:(0,r.jsx)("a",{children:"Docs"})})]}),(0,r.jsx)("div",{children:(0,r.jsx)(l.default,{href:"https://github.com/tfukaza/harvest",children:(0,r.jsx)("a",{className:"".concat(s().button," ").concat(a().github),children:"GitHub"})})})]})}},237:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return i}});var r=n(5893),o=n(4155),a=function(e){var t=o.env.BASE_PATH;return void 0===t&&(t=""),"".concat(t,"/").concat(e)};function i(e){e.props;var t=e.src;return void 0===t?(0,r.jsx)("img",{}):(0,r.jsx)("img",{src:a(t),alt:"img"})}},123:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return v}});var r=n(5893),o=n(4705),a=n(6793),i=n(2833),s=n(3899),l=n(1664),u=n(3679),c=n.n(u),d=n(4139),f=n.n(d),p=n(5016),h=n.n(p),m=JSON.parse('[{"function":"buy(self, symbol, quantity, in_force, extended)","index":"buy","short_description":"Buys the specified asset.","long_description":"When called, Harvests places a limit order with a limit\\nprice 5% higher than the current price.","params":[{"name":"symbol","type":"str","desc":"Symbol of the asset to buy. ","default":"first symbol in watch","optional":true},{"name":"quantity","type":"float","desc":"Quantity of asset to buy. ","default":"1","optional":true},{"name":"in_force","type":"str","desc":"Duration the order is in force. \'{gtc}\' or \'{gtd}\'. ","default":"\'gtc\'","optional":true},{"name":"extended","type":"str","desc":"Whether to trade in extended hours or not. ","default":"False","optional":true}],"returns":"The following Python dictionary\\n- type: str, \'STOCK\' or \'CRYPTO\'\\n- id: str, ID of order\\n- symbol: str, symbol of asset","raises":[{"type":"Exception","desc":"There is an error in the order process."}]},{"function":"buy_option(self, symbol, quantity, in_force)","index":"buy_option","short_description":"Buys the specified option.","long_description":null,"params":[{"name":"symbol","type":"str","desc":"Symbol of the asset to buy, in OCC format","default":null,"optional":true},{"name":"quantity","type":"float","desc":"Quantity of asset to bu","default":null,"optional":true},{"name":"in_force","type":"str","desc":"Duration the order is in forc","default":null,"optional":true}],"returns":"A dictionary with the following keys:\\n- type: \'OPTION\'\\n- id: ID of order\\n- symbol: symbol of asset","raises":[{"type":"Exception","desc":"There is an error in the order process."}]},{"function":"sell(self, symbol, quantity, in_force, extended)","index":"sell","short_description":"Sells the specified asset.","long_description":null,"params":[{"name":"symbol","type":"str","desc":"Symbol of the asset to sel","default":null,"optional":true},{"name":"quantity","type":"float","desc":"Quantity of asset to sel","default":null,"optional":true},{"name":"in_force","type":"str","desc":"Duration the order is in forc","default":null,"optional":true},{"name":"extended","type":"str","desc":"Whether to trade in extended hours or not","default":null,"optional":true}],"returns":"A dictionary with the following keys:\\n- type: str, \'STOCK\' or \'CRYPTO\'\\n- id: str, ID of order\\n- symbol: str, symbol of asset","raises":[{"type":"Exception","desc":"There is an error in the order process."}]},{"function":"sell_option(self, symbol, quantity, in_force)","index":"sell_option","short_description":"Sells the specified option.","long_description":null,"params":[{"name":"symbol","type":"str","desc":"Symbol of the asset to buy, in OCC format","default":null,"optional":true},{"name":"quantity","type":"float","desc":"Quantity of asset to bu","default":null,"optional":true},{"name":"in_force","type":"str","desc":"Duration the order is in forc","default":null,"optional":true}],"returns":"A dictionary with the following keys:\\n- type: \'OPTION\'\\n- id: ID of order\\n- symbol: symbol of asset","raises":[{"type":"Exception","desc":"There is an error in the order process."}]},{"function":"await_buy(self, symbol, quantity, in_force, extended)","index":"await_buy","short_description":"Buys the specified asset, and hangs the code until the order is filled. ","long_description":null,"params":[{"name":"symbol","type":"str","desc":"Symbol of the asset to bu","default":null,"optional":true},{"name":"quantity","type":"float","desc":"Quantity of asset to bu","default":null,"optional":true},{"name":"in_force","type":"str","desc":"Duration the order is in forc","default":null,"optional":true},{"name":"extended","type":"str","desc":"Whether to trade in extended hours or not","default":null,"optional":true}],"returns":"A dictionary with the following keys:\\n- type: \'STOCK\' or \'CRYPTO\'\\n- id: ID of order\\n- symbol: symbol of asset","raises":[{"type":"Exception","desc":"There is an error in the order process."}]},{"function":"await_sell(self, symbol, quantity, in_force, extended)","index":"await_sell","short_description":"Sells the specified asset, and hangs the code until the order is filled. ","long_description":null,"params":[{"name":"symbol","type":"str","desc":"Symbol of the asset to bu","default":null,"optional":true},{"name":"quantity","type":"float","desc":"Quantity of asset to bu","default":null,"optional":true},{"name":"in_force","type":"str","desc":"Duration the order is in forc","default":null,"optional":true},{"name":"extended","type":"str","desc":"Whether to trade in extended hours or not","default":null,"optional":true}],"returns":"A dictionary with the following keys:\\n- type: \'STOCK\' or \'CRYPTO\'\\n- id: ID of order\\n- symbol: symbol of asset","raises":[{"type":"Exception","desc":"There is an error in the order process."}]},{"function":"get_option_market_data(self, symbol)","index":"get_option_market_data","short_description":"Retrieves data of specified option. ","long_description":null,"params":[{"name":"symbol","type":null,"desc":"Occ symbol of optio","default":null,"optional":null}],"returns":"A dictionary:\\n- price: price of option \\n- ask: ask price\\n- bid: bid price\\n}","raises":[]},{"function":"get_chain_data(self, symbol)","index":"get_chain_data","short_description":"Returns the option chain for the specified symbol. ","long_description":null,"params":[{"name":"symbol","type":null,"desc":"symbol of stoc","default":null,"optional":null}],"returns":"A dataframe in the following format:\\n            exp_date strike  type    id\\n    OCC\\n    ---     ---      ---     ---     ---     \\n- OCC: the chain symbol in OCC format","raises":[]},{"function":"get_chain_info(self, symbol)","index":"get_chain_info","short_description":"Returns information about the symbol\'s options","long_description":null,"params":[{"name":"symbol","type":null,"desc":"symbol of stoc","default":null,"optional":null}],"returns":"A dict with the following keys:\\n- id: ID of the option chain \\n- exp_dates: List of expiration dates, in the fomrat \\"YYYY-MM-DD\\" \\n- multiplier: Multiplier of the option, usually 100","raises":[]},{"function":"ema(self, symbol, period, interval, ref)","index":"ema","short_description":"Calculate EMA","long_description":null,"params":[{"name":"symbol","type":null,"desc":"Symbol to perform calculation o","default":null,"optional":null},{"name":"period","type":null,"desc":"Period of EM","default":null,"optional":null},{"name":"interval","type":null,"desc":"Interval to perform the calculatio","default":null,"optional":null},{"name":"ref","type":null,"desc":"\'close\', \'open\', \'high\', or \'low","default":null,"optional":null}],"returns":"A list in numpy format, containing EMA values","raises":[]},{"function":"rsi(self, symbol, period, interval, ref)","index":"rsi","short_description":"Calculate RSI","long_description":null,"params":[{"name":"symbol","type":null,"desc":"Symbol to perform calculation o","default":null,"optional":null},{"name":"period","type":null,"desc":"Period of RS","default":null,"optional":null},{"name":"interval","type":null,"desc":"Interval to perform the calculatio","default":null,"optional":null},{"name":"ref","type":null,"desc":"\'close\', \'open\', \'high\', or \'low","default":null,"optional":null}],"returns":"A list in numpy format, containing RSI values","raises":[]},{"function":"sma(self, symbol, period, interval, ref)","index":"sma","short_description":"Calculate SMA","long_description":null,"params":[{"name":"symbol","type":null,"desc":"Symbol to perform calculation o","default":null,"optional":null},{"name":"period","type":null,"desc":"Period of SM","default":null,"optional":null},{"name":"interval","type":null,"desc":"Interval to perform the calculatio","default":null,"optional":null},{"name":"ref","type":null,"desc":"\'close\', \'open\', \'high\', or \'low","default":null,"optional":null}],"returns":"A list in numpy format, containing SMA values","raises":[]},{"function":"bbands(self, symbol, period, interval, ref, dev)","index":"bbands","short_description":"Calculate Bollinger Bands","long_description":null,"params":[{"name":"symbol","type":null,"desc":"Symbol to perform calculation o","default":null,"optional":null},{"name":"period","type":null,"desc":"Period of BBan","default":null,"optional":null},{"name":"interval","type":null,"desc":"Interval to perform the calculatio","default":null,"optional":null},{"name":"ref","type":null,"desc":"\'close\', \'open\', \'high\', or \'low","default":null,"optional":null},{"name":"dev","type":null,"desc":"Standard deviation of the band","default":null,"optional":null}],"returns":"A tuple of numpy lists, each a list of BBand top, average, and bottom values","raises":[]},{"function":"get_account_buying_power(self)","index":"get_account_buying_power","short_description":null,"long_description":null,"params":[],"returns":"","raises":[]},{"function":"get_account_equity(self)","index":"get_account_equity","short_description":null,"long_description":null,"params":[],"returns":"","raises":[]},{"function":"get_candle(self)","index":"get_candle","short_description":null,"long_description":null,"params":[],"returns":"","raises":[]},{"function":"get_candle_list(self)","index":"get_candle_list","short_description":null,"long_description":null,"params":[],"returns":"","raises":[]},{"function":"get_cost(self, symbol)","index":"get_cost","short_description":"Returns the average cost of a specified asset. ","long_description":null,"params":[{"name":"symbol","type":null,"desc":"Symbol of asse","default":null,"optional":null}],"returns":"Average cost of asset. Returns None if asset is not being tracked.","raises":[]},{"function":"get_date(self)","index":"get_date","short_description":null,"long_description":null,"params":[],"returns":"","raises":[]},{"function":"get_datetime(self)","index":"get_datetime","short_description":null,"long_description":null,"params":[],"returns":"","raises":[]},{"function":"get_price(self)","index":"get_price","short_description":null,"long_description":null,"params":[],"returns":"","raises":[]},{"function":"get_price_list(self, symbol, interval)","index":"get_price_list","short_description":"Returns a list of recent prices for an asset. ","long_description":null,"params":[{"name":"symbol","type":null,"desc":"Symbol of asset","default":null,"optional":null},{"name":"interval","type":null,"desc":"Interval of data","default":null,"optional":null}],"returns":"Average cost of asset. Returns None if asset is not being tracked.","raises":[]},{"function":"get_quantity(self, symbol)","index":"get_quantity","short_description":"Returns the quantity owned of a specified asset. ","long_description":null,"params":[{"name":"symbol","type":null,"desc":"Symbol of asse","default":null,"optional":null}],"returns":"Quantity of asset. 0 if asset is not owned.","raises":[]},{"function":"get_returns(self, symbol)","index":"get_returns","short_description":"Returns the return of a specified asset. ","long_description":null,"params":[{"name":"symbol","type":null,"desc":"Symbol of stock, crypto, or option. Options should be in OCC format","default":null,"optional":null}],"returns":"Return of asset, expressed as a decimal. Returns None if asset is not owned.","raises":[]},{"function":"get_time(self)","index":"get_time","short_description":null,"long_description":null,"params":[],"returns":"","raises":[]},{"function":"get_watch(self)","index":"get_watch","short_description":null,"long_description":null,"params":[],"returns":"","raises":[]}]');function y(e,t){var n;if("undefined"===typeof Symbol||null==e[Symbol.iterator]){if(Array.isArray(e)||(n=function(e,t){if(!e)return;if("string"===typeof e)return _(e,t);var n=Object.prototype.toString.call(e).slice(8,-1);"Object"===n&&e.constructor&&(n=e.constructor.name);if("Map"===n||"Set"===n)return Array.from(e);if("Arguments"===n||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n))return _(e,t)}(e))||t&&e&&"number"===typeof e.length){n&&(e=n);var r=0,o=function(){};return{s:o,n:function(){return r>=e.length?{done:!0}:{done:!1,value:e[r++]}},e:function(e){throw e},f:o}}throw new TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.")}var a,i=!0,s=!1;return{s:function(){n=e[Symbol.iterator]()},n:function(){var e=n.next();return i=e.done,e},e:function(e){s=!0,a=e},f:function(){try{i||null==n.return||n.return()}finally{if(s)throw a}}}}function _(e,t){(null==t||t>e.length)&&(t=e.length);for(var n=0,r=new Array(t);n<t;n++)r[n]=e[n];return r}function v(){var e,t=[],n=[],u=y(m);try{for(u.s();!(e=u.n()).done;){var d=e.value;t.push((0,r.jsx)(s.default,{dict:d})),n.push((0,r.jsx)(l.default,{href:"/docs#"+d.index,passHref:!0,children:(0,r.jsx)("li",{children:d.index})}))}}catch(p){u.e(p)}finally{u.f()}return(0,r.jsxs)("div",{className:c().container,children:[(0,r.jsx)(a.default,{title:"Harvest | Documentation"}),(0,r.jsx)(o.default,{}),(0,r.jsxs)("main",{className:c().main,children:[(0,r.jsxs)("nav",{className:"".concat(f().nav," ").concat(h().card),children:[(0,r.jsx)("h3",{children:"Algo"}),(0,r.jsx)("ul",{children:n})]}),(0,r.jsxs)("section",{className:c().section,children:[(0,r.jsx)("h1",{children:"Documentation"}),(0,r.jsx)("h2",{className:f().className,children:"harvest.Algo"}),t]})]}),(0,r.jsx)(i.default,{})]})}},4653:function(e,t,n){(window.__NEXT_P=window.__NEXT_P||[]).push(["/docs",function(){return n(123)}])},4139:function(e){e.exports={nav:"Doc_nav__2GF3d",className:"Doc_className__38Gp3",entry:"Doc_entry__10WMz",paramHeader:"Doc_paramHeader__3-mXJ",paramReturn:"Doc_paramReturn__35Fxt",paramRaise:"Doc_paramRaise__3igaR",lookup:"Doc_lookup__1eTBB",raises:"Doc_raises__2IpAt"}},5016:function(e){e.exports={button:"rowcrop_button__1n6eZ",card:"rowcrop_card__25eqx",col4:"rowcrop_col4__2ZQay"}},3679:function(e){e.exports={container:"Home_container__3sao-",main:"Home_main__1Z1aG",nav:"Home_nav__2iapp",logo:"Home_logo__3GqVp",github:"Home_github__3XEl-",landing:"Home_landing__2U_o4",section:"Home_section__354aW",text:"Home_text__dq4ii",button:"Home_button__2hScn",col_card:"Home_col_card__6BIVE",col4:"Home_col4__2OXKu",footer:"Home_footer__2v49s"}},9008:function(e,t,n){e.exports=n(2775)},1664:function(e,t,n){e.exports=n(2167)},8164:function(e,t,n){var r=n(4360);e.exports=function(e){if(Array.isArray(e))return r(e)}},1682:function(e){e.exports=function(e,t,n){return t in e?Object.defineProperty(e,t,{value:n,enumerable:!0,configurable:!0,writable:!0}):e[t]=n,e}},7381:function(e){e.exports=function(e){if("undefined"!==typeof Symbol&&Symbol.iterator in Object(e))return Array.from(e)}},5725:function(e){e.exports=function(){throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.")}},3115:function(e,t,n){var r=n(8164),o=n(7381),a=n(3585),i=n(5725);e.exports=function(e){return r(e)||o(e)||a(e)||i()}},4155:function(e){var t,n,r=e.exports={};function o(){throw new Error("setTimeout has not been defined")}function a(){throw new Error("clearTimeout has not been defined")}function i(e){if(t===setTimeout)return setTimeout(e,0);if((t===o||!t)&&setTimeout)return t=setTimeout,setTimeout(e,0);try{return t(e,0)}catch(n){try{return t.call(null,e,0)}catch(n){return t.call(this,e,0)}}}!function(){try{t="function"===typeof setTimeout?setTimeout:o}catch(e){t=o}try{n="function"===typeof clearTimeout?clearTimeout:a}catch(e){n=a}}();var s,l=[],u=!1,c=-1;function d(){u&&s&&(u=!1,s.length?l=s.concat(l):c=-1,l.length&&f())}function f(){if(!u){var e=i(d);u=!0;for(var t=l.length;t;){for(s=l,l=[];++c<t;)s&&s[c].run();c=-1,t=l.length}s=null,u=!1,function(e){if(n===clearTimeout)return clearTimeout(e);if((n===a||!n)&&clearTimeout)return n=clearTimeout,clearTimeout(e);try{n(e)}catch(t){try{return n.call(null,e)}catch(t){return n.call(this,e)}}}(e)}}function p(e,t){this.fun=e,this.array=t}function h(){}r.nextTick=function(e){var t=new Array(arguments.length-1);if(arguments.length>1)for(var n=1;n<arguments.length;n++)t[n-1]=arguments[n];l.push(new p(e,t)),1!==l.length||u||i(f)},p.prototype.run=function(){this.fun.apply(null,this.array)},r.title="browser",r.browser=!0,r.env={},r.argv=[],r.version="",r.versions={},r.on=h,r.addListener=h,r.once=h,r.off=h,r.removeListener=h,r.removeAllListeners=h,r.emit=h,r.prependListener=h,r.prependOnceListener=h,r.listeners=function(e){return[]},r.binding=function(e){throw new Error("process.binding is not supported")},r.cwd=function(){return"/"},r.chdir=function(e){throw new Error("process.chdir is not supported")},r.umask=function(){return 0}}},function(e){e.O(0,[317,774,888,179],(function(){return t=4653,e(e.s=t);var t}));var t=e.O();_N_E=t}]);