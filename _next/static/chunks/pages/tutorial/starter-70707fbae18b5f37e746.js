(self.webpackChunk_N_E=self.webpackChunk_N_E||[]).push([[248],{2167:function(e,t,n){"use strict";var r=n(3848),o=n(9448);t.default=void 0;var a=o(n(7294)),i=n(9414),s=n(4651),l=n(7426),c={};function u(e,t,n,r){if(e&&(0,i.isLocalURL)(t)){e.prefetch(t,n,r).catch((function(e){0}));var o=r&&"undefined"!==typeof r.locale?r.locale:e&&e.locale;c[t+"%"+n+(o?"%"+o:"")]=!0}}var d=function(e){var t,n=!1!==e.prefetch,o=(0,s.useRouter)(),d=a.default.useMemo((function(){var t=(0,i.resolveHref)(o,e.href,!0),n=r(t,2),a=n[0],s=n[1];return{href:a,as:e.as?(0,i.resolveHref)(o,e.as):s||a}}),[o,e.href,e.as]),f=d.href,h=d.as,p=e.children,m=e.replace,v=e.shallow,g=e.scroll,y=e.locale;"string"===typeof p&&(p=a.default.createElement("a",null,p));var b=(t=a.Children.only(p))&&"object"===typeof t&&t.ref,x=(0,l.useIntersection)({rootMargin:"200px"}),_=r(x,2),w=_[0],j=_[1],k=a.default.useCallback((function(e){w(e),b&&("function"===typeof b?b(e):"object"===typeof b&&(b.current=e))}),[b,w]);(0,a.useEffect)((function(){var e=j&&n&&(0,i.isLocalURL)(f),t="undefined"!==typeof y?y:o&&o.locale,r=c[f+"%"+h+(t?"%"+t:"")];e&&!r&&u(o,f,h,{locale:t})}),[h,f,j,y,n,o]);var T={ref:k,onClick:function(e){t.props&&"function"===typeof t.props.onClick&&t.props.onClick(e),e.defaultPrevented||function(e,t,n,r,o,a,s,l){("A"!==e.currentTarget.nodeName||!function(e){var t=e.currentTarget.target;return t&&"_self"!==t||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.nativeEvent&&2===e.nativeEvent.which}(e)&&(0,i.isLocalURL)(n))&&(e.preventDefault(),null==s&&r.indexOf("#")>=0&&(s=!1),t[o?"replace":"push"](n,r,{shallow:a,locale:l,scroll:s}))}(e,o,f,h,m,v,g,y)},onMouseEnter:function(e){(0,i.isLocalURL)(f)&&(t.props&&"function"===typeof t.props.onMouseEnter&&t.props.onMouseEnter(e),u(o,f,h,{priority:!0}))}};if(e.passHref||"a"===t.type&&!("href"in t.props)){var O="undefined"!==typeof y?y:o&&o.locale,M=o&&o.isLocaleDomain&&(0,i.getDomainLocale)(h,O,o&&o.locales,o&&o.domainLocales);T.href=M||(0,i.addBasePath)((0,i.addLocale)(h,O,o&&o.defaultLocale))}return a.default.cloneElement(t,T)};t.default=d},7426:function(e,t,n){"use strict";var r=n(3848);t.__esModule=!0,t.useIntersection=function(e){var t=e.rootMargin,n=e.disabled||!i,l=(0,o.useRef)(),c=(0,o.useState)(!1),u=r(c,2),d=u[0],f=u[1],h=(0,o.useCallback)((function(e){l.current&&(l.current(),l.current=void 0),n||d||e&&e.tagName&&(l.current=function(e,t,n){var r=function(e){var t=e.rootMargin||"",n=s.get(t);if(n)return n;var r=new Map,o=new IntersectionObserver((function(e){e.forEach((function(e){var t=r.get(e.target),n=e.isIntersecting||e.intersectionRatio>0;t&&n&&t(n)}))}),e);return s.set(t,n={id:t,observer:o,elements:r}),n}(n),o=r.id,a=r.observer,i=r.elements;return i.set(e,t),a.observe(e),function(){i.delete(e),a.unobserve(e),0===i.size&&(a.disconnect(),s.delete(o))}}(e,(function(e){return e&&f(e)}),{rootMargin:t}))}),[n,t,d]);return(0,o.useEffect)((function(){if(!i&&!d){var e=(0,a.requestIdleCallback)((function(){return f(!0)}));return function(){return(0,a.cancelIdleCallback)(e)}}}),[d]),[h,d]};var o=n(7294),a=n(3447),i="undefined"!==typeof IntersectionObserver;var s=new Map},3398:function(e,t,n){"use strict";var r;t.__esModule=!0,t.AmpStateContext=void 0;var o=((r=n(7294))&&r.__esModule?r:{default:r}).default.createContext({});t.AmpStateContext=o},6393:function(e,t,n){"use strict";t.__esModule=!0,t.isInAmpMode=i,t.useAmp=function(){return i(o.default.useContext(a.AmpStateContext))};var r,o=(r=n(7294))&&r.__esModule?r:{default:r},a=n(3398);function i(){var e=arguments.length>0&&void 0!==arguments[0]?arguments[0]:{},t=e.ampFirst,n=void 0!==t&&t,r=e.hybrid,o=void 0!==r&&r,a=e.hasQuery,i=void 0!==a&&a;return n||o&&i}},2775:function(e,t,n){"use strict";var r=n(1682);function o(e,t){var n=Object.keys(e);if(Object.getOwnPropertySymbols){var r=Object.getOwnPropertySymbols(e);t&&(r=r.filter((function(t){return Object.getOwnPropertyDescriptor(e,t).enumerable}))),n.push.apply(n,r)}return n}t.__esModule=!0,t.defaultHead=f,t.default=void 0;var a,i=function(e){if(e&&e.__esModule)return e;if(null===e||"object"!==typeof e&&"function"!==typeof e)return{default:e};var t=d();if(t&&t.has(e))return t.get(e);var n={},r=Object.defineProperty&&Object.getOwnPropertyDescriptor;for(var o in e)if(Object.prototype.hasOwnProperty.call(e,o)){var a=r?Object.getOwnPropertyDescriptor(e,o):null;a&&(a.get||a.set)?Object.defineProperty(n,o,a):n[o]=e[o]}n.default=e,t&&t.set(e,n);return n}(n(7294)),s=(a=n(3244))&&a.__esModule?a:{default:a},l=n(3398),c=n(1165),u=n(6393);function d(){if("function"!==typeof WeakMap)return null;var e=new WeakMap;return d=function(){return e},e}function f(){var e=arguments.length>0&&void 0!==arguments[0]&&arguments[0],t=[i.default.createElement("meta",{charSet:"utf-8"})];return e||t.push(i.default.createElement("meta",{name:"viewport",content:"width=device-width"})),t}function h(e,t){return"string"===typeof t||"number"===typeof t?e:t.type===i.default.Fragment?e.concat(i.default.Children.toArray(t.props.children).reduce((function(e,t){return"string"===typeof t||"number"===typeof t?e:e.concat(t)}),[])):e.concat(t)}var p=["name","httpEquiv","charSet","itemProp"];function m(e,t){return e.reduce((function(e,t){var n=i.default.Children.toArray(t.props.children);return e.concat(n)}),[]).reduce(h,[]).reverse().concat(f(t.inAmpMode)).filter(function(){var e=new Set,t=new Set,n=new Set,r={};return function(o){var a=!0,i=!1;if(o.key&&"number"!==typeof o.key&&o.key.indexOf("$")>0){i=!0;var s=o.key.slice(o.key.indexOf("$")+1);e.has(s)?a=!1:e.add(s)}switch(o.type){case"title":case"base":t.has(o.type)?a=!1:t.add(o.type);break;case"meta":for(var l=0,c=p.length;l<c;l++){var u=p[l];if(o.props.hasOwnProperty(u))if("charSet"===u)n.has(u)?a=!1:n.add(u);else{var d=o.props[u],f=r[u]||new Set;"name"===u&&i||!f.has(d)?(f.add(d),r[u]=f):a=!1}}}return a}}()).reverse().map((function(e,n){var a=e.key||n;if(!t.inAmpMode&&"link"===e.type&&e.props.href&&["https://fonts.googleapis.com/css","https://use.typekit.net/"].some((function(t){return e.props.href.startsWith(t)}))){var s=function(e){for(var t=1;t<arguments.length;t++){var n=null!=arguments[t]?arguments[t]:{};t%2?o(Object(n),!0).forEach((function(t){r(e,t,n[t])})):Object.getOwnPropertyDescriptors?Object.defineProperties(e,Object.getOwnPropertyDescriptors(n)):o(Object(n)).forEach((function(t){Object.defineProperty(e,t,Object.getOwnPropertyDescriptor(n,t))}))}return e}({},e.props||{});return s["data-href"]=s.href,s.href=void 0,s["data-optimized-fonts"]=!0,i.default.cloneElement(e,s)}return i.default.cloneElement(e,{key:a})}))}var v=function(e){var t=e.children,n=(0,i.useContext)(l.AmpStateContext),r=(0,i.useContext)(c.HeadManagerContext);return i.default.createElement(s.default,{reduceComponentsToState:m,headManager:r,inAmpMode:(0,u.isInAmpMode)(n)},t)};t.default=v},3244:function(e,t,n){"use strict";var r=n(3115),o=n(2553),a=n(2012),i=(n(450),n(9807)),s=n(7690),l=n(9828);function c(e){var t=function(){if("undefined"===typeof Reflect||!Reflect.construct)return!1;if(Reflect.construct.sham)return!1;if("function"===typeof Proxy)return!0;try{return Date.prototype.toString.call(Reflect.construct(Date,[],(function(){}))),!0}catch(e){return!1}}();return function(){var n,r=l(e);if(t){var o=l(this).constructor;n=Reflect.construct(r,arguments,o)}else n=r.apply(this,arguments);return s(this,n)}}t.__esModule=!0,t.default=void 0;var u=n(7294),d=function(e){i(n,e);var t=c(n);function n(e){var a;return o(this,n),(a=t.call(this,e))._hasHeadManager=void 0,a.emitChange=function(){a._hasHeadManager&&a.props.headManager.updateHead(a.props.reduceComponentsToState(r(a.props.headManager.mountedInstances),a.props))},a._hasHeadManager=a.props.headManager&&a.props.headManager.mountedInstances,a}return a(n,[{key:"componentDidMount",value:function(){this._hasHeadManager&&this.props.headManager.mountedInstances.add(this),this.emitChange()}},{key:"componentDidUpdate",value:function(){this.emitChange()}},{key:"componentWillUnmount",value:function(){this._hasHeadManager&&this.props.headManager.mountedInstances.delete(this),this.emitChange()}},{key:"render",value:function(){return null}}]),n}(u.Component);t.default=d},1536:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return a}});var r=n(5893),o=n(7317);function a(e){var t=e.lang,n=e.value;return void 0===t&&(t="text"),void 0===n&&(n="Hello World"),(0,r.jsx)(o.Z,{language:t,customStyle:"",useInlineStyles:!1,children:n})}},2833:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return l}});var r=n(5893),o=n(3679),a=n.n(o),i=n(1664),s=n(237);function l(){return(0,r.jsx)("footer",{className:a().footer,children:(0,r.jsxs)("section",{className:a().section,children:[(0,r.jsxs)("div",{children:[(0,r.jsx)(s.default,{src:"/wordmark.svg"}),(0,r.jsx)(i.default,{href:"https://github.com/tfukaza/harvest/issues/new?assignees=&labels=bug&template=bug_report.md&title=%5B%F0%9F%AA%B0BUG%5D",children:"Report a Bug"}),(0,r.jsx)(i.default,{href:"https://github.com/tfukaza/harvest/issues/new?assignees=&labels=enhancement%2C+question&template=feature-request.md&title=%5B%F0%9F%92%A1Feature+Request%5D",children:"Suggest a Feature"})]}),(0,r.jsxs)("div",{children:[(0,r.jsx)("h3",{children:"Special thanks to these projects:"}),(0,r.jsx)(i.default,{href:"https://github.com/jmfernandes/robin_stocks",children:"robin_stocks"})]})]})})}},6793:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return a}});var r=n(5893),o=n(9008);function a(e){e.c;var t=e.title;return(0,r.jsxs)(o.default,{children:[(0,r.jsx)("title",{children:t}),(0,r.jsx)("meta",{name:"description",content:""}),(0,r.jsx)("meta",{name:"viewport",content:"width=device-width, initial-scale=1.0"}),(0,r.jsx)("meta",{property:"og:title",content:t}),(0,r.jsx)("meta",{property:"og:type",content:"website"}),(0,r.jsx)("meta",{property:"og:image",content:"/img/wordmark.svg"}),(0,r.jsx)("link",{rel:"icon",href:"/favicon.ico"})]})}},4705:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return u}});var r=n(5893),o=n(3679),a=n.n(o),i=n(5016),s=n.n(i),l=n(1664),c=n(237);function u(){return(0,r.jsxs)("nav",{className:a().nav,children:[(0,r.jsx)("div",{children:(0,r.jsx)(l.default,{href:"/",passHref:!0,children:(0,r.jsx)("a",{id:a().logo,children:(0,r.jsx)(c.default,{src:"/wordmark.svg"})})})}),(0,r.jsxs)("div",{children:[(0,r.jsx)(l.default,{href:"/tutorial",children:(0,r.jsx)("a",{children:"Tutorials"})}),(0,r.jsx)(l.default,{href:"/docs",children:(0,r.jsx)("a",{children:"Docs"})})]}),(0,r.jsx)("div",{children:(0,r.jsx)(l.default,{href:"https://github.com/tfukaza/harvest",children:(0,r.jsx)("a",{className:"".concat(s().button," ").concat(a().github),children:"GitHub"})})})]})}},237:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return i}});var r=n(5893),o=n(4155),a=function(e){var t=e.src;return"{".concat(o.env.BASE_PATH,"/").concat(t,"}")};function i(e){e.props;var t=e.src;return void 0===t?(0,r.jsx)("img",{}):(0,r.jsx)("img",{src:a(t),alt:"img"})}},7718:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return u}});var r=n(5893),o=n(4705),a=n(6793),i=n(2833),s=n(1536),l=n(3679),c=n.n(l);function u(){return(0,r.jsxs)("div",{className:c().container,children:[(0,r.jsx)(a.default,{title:"Harvest | Tutorials"}),(0,r.jsx)(o.default,{}),(0,r.jsxs)("main",{className:c().main,children:[(0,r.jsx)("section",{}),(0,r.jsx)("section",{className:c().section,children:(0,r.jsxs)("div",{className:c().text,children:[(0,r.jsx)("h1",{children:"Startup Guide"}),(0,r.jsx)("h2",{children:"Prerequisites"}),(0,r.jsx)("p",{children:"Before we begin, make sure you have the following:"}),(0,r.jsxs)("ul",{children:[(0,r.jsx)("li",{children:"Python, version 3.8 or higher."}),(0,r.jsx)("li",{children:"A code editing software."}),(0,r.jsx)("li",{children:"An account for a brokerage. In this tutorial we will be using Robinhood."}),(0,r.jsx)("li",{children:"Basic coding skills. If you've written anything more than 'Hello World', you should be good to go."})]}),(0,r.jsx)("h2",{children:"Installing"}),(0,r.jsx)("p",{children:"First things first, let's install the library. "}),(0,r.jsx)(s.default,{lang:"bash",value:"pip install -e git+https://github.com/tfukaza/harvest.git"}),(0,r.jsx)("p",{children:"Next, we install additional libraries depending on which broker you want to use. Harvest will do this automatically, using the following command:"}),(0,r.jsx)(s.default,{lang:"bash",value:"pip install -e git+https://github.com/tfukaza/harvest.git#egg=harvest[BROKER]"}),(0,r.jsx)("p",{children:"Where BROKER is replaced by one of the following brokers supported by Harvest:"}),(0,r.jsx)("ul",{children:(0,r.jsx)("li",{children:"Robinhood"})}),(0,r.jsx)("p",{children:"On MacOS's zsh, you will need to use the following format instead:"}),(0,r.jsx)(s.default,{lang:"bash",value:"pip install -e 'git+https://github.com/tfukaza/harvest.git#egg=harvest[BROKER]'"}),(0,r.jsx)("h2",{children:"Example Code"}),(0,r.jsx)("p",{children:"Once you have everything installed, we are ready to begin writing the code. For this example we will use Robinhood, but the code is still mostly the same if you decide to use other brokers. Before we begin, there are three components of Harvest you need to know:"}),(0,r.jsxs)("ul",{children:[(0,r.jsx)("li",{children:"Trader: The main module responsible for managing the other modules."}),(0,r.jsx)("li",{children:"Broker: The module that communicates with the brokerage you are using."}),(0,r.jsx)("li",{children:"Algo: The module where you define your algorithm."})]}),(0,r.jsx)("p",{children:"We begin coding by import the aforementioned components, or 'modules' as they are called in Python."}),(0,r.jsx)(s.default,{lang:"python",value:"from harvest.algo import BaseAlgo\nfrom harvest.trader import Trader\nfrom harvest.broker.robinhood import RobinhoodBroker"}),(0,r.jsx)("p",{children:"Then we create a Trader, which will be the starting point of Harvest"}),(0,r.jsx)(s.default,{lang:"python",value:'if __name__ == "__main__":\nt = Trader( RobinhoodBroker() )'}),(0,r.jsx)("p",{children:"Few things happen here, and don't worry, this is as complex as Harvest will get (for now). The trader class is instantiated. Traders take two Brokers as input, a streamer and a broker. streamer is the broker used to retrieve stock/cryto data. broker is the brokerage used to place orders and manage your portfolio. For this example, we initialize RobinhoodBroker. The broker automatically reads the credentials saved in secret.yaml and sets up a connection with the broker. The Robinhood broker is specified as a streamer and will be used to get stock/crypto data. If the broker is unspecified, Robinhood will also be used as a broker. Fortunately after this, things get pretty easy. We specify what stock to track, in this case Twitter (TWTR)."}),(0,r.jsx)(s.default,{lang:"python",value:"t.add_symbol('TWTR')"}),(0,r.jsx)("p",{children:"At this point, we define our algorithm. Algorithms are created by extending the BaseAlgo class."}),(0,r.jsx)(s.default,{lang:"python",value:"class Twitter(BaseAlgo):\n                    def algo_init(self):\n                        pass\n\n                    def handler(self, meta):\n                        pass"}),(0,r.jsx)("p",{children:"every Algo must define two functions algo_init: Function called right before the algorithm starts handler: Function called at a specified interval. In this example, we create a simple algorithm that buys and sells a single stock."}),(0,r.jsx)(s.default,{lang:"python",value:"class Twitter(BaseAlgo):\n    def algo_init(self):\n        self.hold = False\n\n    def handler(self, meta):\n        if self.hold:\n            self.sell('TWTR', 1)\n            self.hold = False\n        else:\n            self.buy('TWTR', 1)\n            self.hold = True"}),(0,r.jsx)("p",{children:"Finally, we tell the trader to use this algorithm, and run it. Below is the final code after putting everything together."}),(0,r.jsx)(s.default,{lang:"python",value:"from harvest.algo import BaseAlgo\nfrom harvest.trader import Trader\nfrom harvest.broker.robinhood import RobinhoodBroker\n\nclass Twitter(BaseAlgo):\n    def algo_init(self):\n        self.hold = False\n\n    def handler(self, meta):\n        if self.hold:\n            self.sell('TWTR', 1)    \n            self.hold = False\n        else:\n            self.buy('TWTR', 1)\n            self.hold = True\n\nif __name__ == \"__main__\":\n    t = Trader( RobinhoodBroker(), None )\n    t.add_symbol('TWTR')\n    t.set_algo(Twitter())\n    t.run(interval='1DAY')"}),(0,r.jsx)("p",{children:"By specifying interval='1DAY' in run, the handler function will be called once every day."}),(0,r.jsx)("p",{children:"Now run the code. If this is the first time connecting to Robinhood, you should see a setup wizard pop up. Follow the steps to set up login credentials for Robinhood."})]})})]}),(0,r.jsx)(i.default,{})]})}},7394:function(e,t,n){(window.__NEXT_P=window.__NEXT_P||[]).push(["/tutorial/starter",function(){return n(7718)}])},5016:function(e){e.exports={button:"rowcrop_button__1n6eZ",card:"rowcrop_card__25eqx",col4:"rowcrop_col4__2ZQay"}},3679:function(e){e.exports={container:"Home_container__3sao-",main:"Home_main__1Z1aG",nav:"Home_nav__2iapp",logo:"Home_logo__3GqVp",github:"Home_github__3XEl-",landing:"Home_landing__2U_o4",section:"Home_section__354aW",text:"Home_text__dq4ii",button:"Home_button__2hScn",col_card:"Home_col_card__6BIVE",col4:"Home_col4__2OXKu",footer:"Home_footer__2v49s"}},9008:function(e,t,n){e.exports=n(2775)},1664:function(e,t,n){e.exports=n(2167)},8164:function(e,t,n){var r=n(4360);e.exports=function(e){if(Array.isArray(e))return r(e)}},1682:function(e){e.exports=function(e,t,n){return t in e?Object.defineProperty(e,t,{value:n,enumerable:!0,configurable:!0,writable:!0}):e[t]=n,e}},7381:function(e){e.exports=function(e){if("undefined"!==typeof Symbol&&Symbol.iterator in Object(e))return Array.from(e)}},5725:function(e){e.exports=function(){throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.")}},3115:function(e,t,n){var r=n(8164),o=n(7381),a=n(3585),i=n(5725);e.exports=function(e){return r(e)||o(e)||a(e)||i()}},4155:function(e){var t,n,r=e.exports={};function o(){throw new Error("setTimeout has not been defined")}function a(){throw new Error("clearTimeout has not been defined")}function i(e){if(t===setTimeout)return setTimeout(e,0);if((t===o||!t)&&setTimeout)return t=setTimeout,setTimeout(e,0);try{return t(e,0)}catch(n){try{return t.call(null,e,0)}catch(n){return t.call(this,e,0)}}}!function(){try{t="function"===typeof setTimeout?setTimeout:o}catch(e){t=o}try{n="function"===typeof clearTimeout?clearTimeout:a}catch(e){n=a}}();var s,l=[],c=!1,u=-1;function d(){c&&s&&(c=!1,s.length?l=s.concat(l):u=-1,l.length&&f())}function f(){if(!c){var e=i(d);c=!0;for(var t=l.length;t;){for(s=l,l=[];++u<t;)s&&s[u].run();u=-1,t=l.length}s=null,c=!1,function(e){if(n===clearTimeout)return clearTimeout(e);if((n===a||!n)&&clearTimeout)return n=clearTimeout,clearTimeout(e);try{n(e)}catch(t){try{return n.call(null,e)}catch(t){return n.call(this,e)}}}(e)}}function h(e,t){this.fun=e,this.array=t}function p(){}r.nextTick=function(e){var t=new Array(arguments.length-1);if(arguments.length>1)for(var n=1;n<arguments.length;n++)t[n-1]=arguments[n];l.push(new h(e,t)),1!==l.length||c||i(f)},h.prototype.run=function(){this.fun.apply(null,this.array)},r.title="browser",r.browser=!0,r.env={},r.argv=[],r.version="",r.versions={},r.on=p,r.addListener=p,r.once=p,r.off=p,r.removeListener=p,r.removeAllListeners=p,r.emit=p,r.prependListener=p,r.prependOnceListener=p,r.listeners=function(e){return[]},r.binding=function(e){throw new Error("process.binding is not supported")},r.cwd=function(){return"/"},r.chdir=function(e){throw new Error("process.chdir is not supported")},r.umask=function(){return 0}}},function(e){e.O(0,[317,774,888,179],(function(){return t=7394,e(e.s=t);var t}));var t=e.O();_N_E=t}]);