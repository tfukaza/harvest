(self.webpackChunk_N_E=self.webpackChunk_N_E||[]).push([[172],{2167:function(e,t,n){"use strict";var r=n(3848),s=n(9448);t.default=void 0;var o=s(n(7294)),i=n(9414),a=n(4651),l=n(7426),c={};function u(e,t,n,r){if(e&&(0,i.isLocalURL)(t)){e.prefetch(t,n,r).catch((function(e){0}));var s=r&&"undefined"!==typeof r.locale?r.locale:e&&e.locale;c[t+"%"+n+(s?"%"+s:"")]=!0}}var d=function(e){var t,n=!1!==e.prefetch,s=(0,a.useRouter)(),d=o.default.useMemo((function(){var t=(0,i.resolveHref)(s,e.href,!0),n=r(t,2),o=n[0],a=n[1];return{href:o,as:e.as?(0,i.resolveHref)(s,e.as):a||o}}),[s,e.href,e.as]),f=d.href,p=d.as,h=e.children,m=e.replace,y=e.shallow,g=e.scroll,_=e.locale;"string"===typeof h&&(h=o.default.createElement("a",null,h));var b=(t=o.Children.only(h))&&"object"===typeof t&&t.ref,v=(0,l.useIntersection)({rootMargin:"200px"}),x=r(v,2),w=x[0],j=x[1],k=o.default.useCallback((function(e){w(e),b&&("function"===typeof b?b(e):"object"===typeof b&&(b.current=e))}),[b,w]);(0,o.useEffect)((function(){var e=j&&n&&(0,i.isLocalURL)(f),t="undefined"!==typeof _?_:s&&s.locale,r=c[f+"%"+p+(t?"%"+t:"")];e&&!r&&u(s,f,p,{locale:t})}),[p,f,j,_,n,s]);var T={ref:k,onClick:function(e){t.props&&"function"===typeof t.props.onClick&&t.props.onClick(e),e.defaultPrevented||function(e,t,n,r,s,o,a,l){("A"!==e.currentTarget.nodeName||!function(e){var t=e.currentTarget.target;return t&&"_self"!==t||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.nativeEvent&&2===e.nativeEvent.which}(e)&&(0,i.isLocalURL)(n))&&(e.preventDefault(),null==a&&r.indexOf("#")>=0&&(a=!1),t[s?"replace":"push"](n,r,{shallow:o,locale:l,scroll:a}))}(e,s,f,p,m,y,g,_)},onMouseEnter:function(e){(0,i.isLocalURL)(f)&&(t.props&&"function"===typeof t.props.onMouseEnter&&t.props.onMouseEnter(e),u(s,f,p,{priority:!0}))}};if(e.passHref||"a"===t.type&&!("href"in t.props)){var S="undefined"!==typeof _?_:s&&s.locale,N=s&&s.isLocaleDomain&&(0,i.getDomainLocale)(p,S,s&&s.locales,s&&s.domainLocales);T.href=N||(0,i.addBasePath)((0,i.addLocale)(p,S,s&&s.defaultLocale))}return o.default.cloneElement(t,T)};t.default=d},7426:function(e,t,n){"use strict";var r=n(3848);t.__esModule=!0,t.useIntersection=function(e){var t=e.rootMargin,n=e.disabled||!i,l=(0,s.useRef)(),c=(0,s.useState)(!1),u=r(c,2),d=u[0],f=u[1],p=(0,s.useCallback)((function(e){l.current&&(l.current(),l.current=void 0),n||d||e&&e.tagName&&(l.current=function(e,t,n){var r=function(e){var t=e.rootMargin||"",n=a.get(t);if(n)return n;var r=new Map,s=new IntersectionObserver((function(e){e.forEach((function(e){var t=r.get(e.target),n=e.isIntersecting||e.intersectionRatio>0;t&&n&&t(n)}))}),e);return a.set(t,n={id:t,observer:s,elements:r}),n}(n),s=r.id,o=r.observer,i=r.elements;return i.set(e,t),o.observe(e),function(){i.delete(e),o.unobserve(e),0===i.size&&(o.disconnect(),a.delete(s))}}(e,(function(e){return e&&f(e)}),{rootMargin:t}))}),[n,t,d]);return(0,s.useEffect)((function(){if(!i&&!d){var e=(0,o.requestIdleCallback)((function(){return f(!0)}));return function(){return(0,o.cancelIdleCallback)(e)}}}),[d]),[p,d]};var s=n(7294),o=n(3447),i="undefined"!==typeof IntersectionObserver;var a=new Map},1536:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return o}});var r=n(5893),s=n(7317);function o(e){var t=e.lang,n=e.value;return void 0===t&&(t="text"),void 0===n&&(n="Hello World"),(0,r.jsx)(s.Z,{language:t,customStyle:"",useInlineStyles:!1,children:n})}},2833:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return l}});var r=n(5893),s=n(3679),o=n.n(s),i=n(1664),a=n(237);function l(){return(0,r.jsx)("footer",{className:o().footer,children:(0,r.jsxs)("section",{className:o().section,children:[(0,r.jsxs)("div",{children:[(0,r.jsx)(a.default,{src:"/wordmark.svg"}),(0,r.jsx)(i.default,{href:"https://github.com/tfukaza/harvest/issues/new?assignees=&labels=bug&template=bug_report.md&title=%5B%F0%9F%AA%B0BUG%5D",children:"Report a Bug"}),(0,r.jsx)(i.default,{href:"https://github.com/tfukaza/harvest/issues/new?assignees=&labels=enhancement%2C+question&template=feature-request.md&title=%5B%F0%9F%92%A1Feature+Request%5D",children:"Suggest a Feature"})]}),(0,r.jsxs)("div",{children:[(0,r.jsx)("h3",{children:"Special thanks to these projects:"}),(0,r.jsx)(i.default,{href:"https://github.com/jmfernandes/robin_stocks",children:"robin_stocks"})]})]})})}},3899:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return f}});var r=n(5893),s=n(4139),o=n.n(s),i=n(1536),a=JSON.parse('{"gtc":"Good-Til-Cancelled. Order will be pending until it is filled or cancelled","gtd":"Good-Til-Day. If the order is not filled by the end of the trading day, it will be cancelled","OCC":"A standard for identifying option securities. See <a href=\'https://en.wikipedia.org/wiki/Option_symbol\'>the Wikipedia page</a> for details."}');function l(e,t){var n;if("undefined"===typeof Symbol||null==e[Symbol.iterator]){if(Array.isArray(e)||(n=function(e,t){if(!e)return;if("string"===typeof e)return c(e,t);var n=Object.prototype.toString.call(e).slice(8,-1);"Object"===n&&e.constructor&&(n=e.constructor.name);if("Map"===n||"Set"===n)return Array.from(e);if("Arguments"===n||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n))return c(e,t)}(e))||t&&e&&"number"===typeof e.length){n&&(e=n);var r=0,s=function(){};return{s:s,n:function(){return r>=e.length?{done:!0}:{done:!1,value:e[r++]}},e:function(e){throw e},f:s}}throw new TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.")}var o,i=!0,a=!1;return{s:function(){n=e[Symbol.iterator]()},n:function(){var e=n.next();return i=e.done,e},e:function(e){a=!0,o=e},f:function(){try{i||null==n.return||n.return()}finally{if(a)throw o}}}}function c(e,t){(null==t||t>e.length)&&(t=e.length);for(var n=0,r=new Array(t);n<t;n++)r[n]=e[n];return r}function u(e){return e in a?a[e]:"404"}function d(e){void 0===e&&(e="");var t,n=/{[^{}]+}/g,s=e.match(n),i=[],a="",c=null,d=l(e.split(n));try{for(d.s();!(t=d.n()).done;){var f=t.value;i.push(f),null!==s&&s.length>0&&(a=s.shift().replace(/[{}]/g,""),c=(0,r.jsx)("span",{dangerouslySetInnerHTML:{__html:u(a)}}),i.push((0,r.jsxs)("span",{className:o().lookup,children:[c,a]})))}}catch(p){d.e(p)}finally{d.f()}return[i,s]}function f(e){var t=e.dict;if(void 0===t)return(0,r.jsx)("p",{children:":)"});var n=function(e){var t,n=[],s=l(e.params);try{for(s.s();!(t=s.n()).done;){var i=t.value,a=d(i.desc);n.push((0,r.jsxs)("div",{children:[(0,r.jsxs)("p",{className:o().paramName,children:["\u2022 ",i.name]}),(0,r.jsxs)("p",{className:o().paramType,children:["\xa0(",i.type,"):"]}),(0,r.jsx)("p",{children:a[0]}),(0,r.jsx)("p",{className:o().paramDef,children:i.default}),(0,r.jsx)("p",{children:a[1]})]}))}}catch(c){s.e(c)}finally{s.f()}return n}(t),s=function(e){var t,n=[],s=l(e.raises);try{for(s.s();!(t=s.n()).done;){var o=t.value;n.push((0,r.jsxs)("li",{children:[(0,r.jsx)("span",{children:o.type+": "}),o.desc]}))}}catch(i){s.e(i)}finally{s.f()}return n}(t),a=function(e){var t,n=[],s=e.returns,o=s.match(/(\s*\n\s*- .+)+/g),i=l(s.split(/\s*- [^\n]*/).filter((function(e){return e.length>0})));try{for(i.s();!(t=i.n()).done;){var a=t.value;if(n.push((0,r.jsx)("p",{children:a})),null!==o&&o.length>0){var c,u=o.shift().match(/-.*[^\n]/g),d=[],f=l(u);try{for(f.s();!(c=f.n()).done;){var p=c.value;d.push((0,r.jsx)("li",{children:p.replace(/- /,"")}))}}catch(h){f.e(h)}finally{f.f()}n.push((0,r.jsx)("ul",{children:d}))}}}catch(h){i.e(h)}finally{i.f()}return n}(t);return(0,r.jsxs)("div",{className:o().entry,id:t.index,children:[(0,r.jsx)(i.default,{lang:"python",value:t.function}),(0,r.jsx)("p",{children:t.short_description}),(0,r.jsx)("p",{className:o().longDesc,children:t.long_description}),(0,r.jsxs)("div",{className:o().paramHeader,children:[(0,r.jsx)("h3",{children:"Params:"}),(0,r.jsx)("h4",{children:"Default"}),n]}),(0,r.jsxs)("div",{className:o().paramReturn,children:[(0,r.jsx)("h3",{children:"Returns:"}),a]}),(0,r.jsxs)("div",{className:o().paramRaise,children:[(0,r.jsx)("h3",{children:"Raises:"}),(0,r.jsx)("ul",{className:o().raises,children:s})]})]})}a.returns},4705:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return u}});var r=n(5893),s=n(3679),o=n.n(s),i=n(5016),a=n.n(i),l=n(1664),c=n(237);function u(){return(0,r.jsxs)("nav",{className:o().nav,children:[(0,r.jsx)("div",{children:(0,r.jsx)(l.default,{href:"/",passHref:!0,children:(0,r.jsx)("a",{id:o().logo,children:(0,r.jsx)(c.default,{src:"/wordmark.svg"})})})}),(0,r.jsxs)("div",{children:[(0,r.jsx)(l.default,{href:"/tutorial",children:(0,r.jsx)("a",{children:"Tutorials"})}),(0,r.jsx)(l.default,{href:"/docs",children:(0,r.jsx)("a",{children:"Docs"})})]}),(0,r.jsx)("div",{children:(0,r.jsx)(l.default,{href:"https://github.com/tfukaza/harvest",children:(0,r.jsx)("a",{className:"".concat(a().button," ").concat(o().github),children:"GitHub"})})})]})}},2966:function(e,t,n){"use strict";n.r(t),n.d(t,{default:function(){return b}});var r=n(5893),s=n(4705),o=n(6793),i=n(2833),a=n(3899),l=(n(1664),n(3679)),c=n.n(l),u=n(4139),d=n.n(u),f=n(5016),p=n.n(f),h=JSON.parse('[{"function":"buy(self, symbol, quantity, in_force, extended)","index":"buy","short_description":"Buys the specified asset.","long_description":"When called, a limit buy order is placed with a limit\\nprice 5% higher than the current price.","params":[{"name":"symbol","type":"str","desc":"Symbol of the asset to buy. ","default":"first symbol in watchlist","optional":true},{"name":"quantity","type":"float","desc":"Quantity of asset to buy. ","default":"buys as many as possible","optional":true},{"name":"in_force","type":"str","desc":"Duration the order is in force. \'{gtc}\' or \'{gtd}\'. ","default":"\'gtc\'","optional":true},{"name":"extended","type":"str","desc":"Whether to trade in extended hours or not. ","default":"False","optional":true}],"returns":"The following Python dictionary\\n- type: str, \'STOCK\' or \'CRYPTO\'\\n- id: str, ID of order\\n- symbol: str, symbol of asset","raises":[{"type":"Exception","desc":"There is an error in the order process."}]},{"function":"buy_option(self, symbol, quantity, in_force)","index":"buy_option","short_description":"Buys the specified option.","long_description":"When called, a limit buy order is placed with a limit\\nprice 5% higher than the current price.","params":[{"name":"symbol","type":"str","desc":"Symbol of the asset to buy, in {OCC} format","default":null,"optional":false},{"name":"quantity","type":"float","desc":"Quantity of asset to buy. ","default":"buys as many as possible","optional":true},{"name":"in_force","type":"str","desc":"Duration the order is in force. \'{gtc}\' or \'{gtd}\'. ","default":"\'gtc\'","optional":true}],"returns":"A dictionary with the following keys:\\n- type: \'OPTION\'\\n- id: ID of order\\n- symbol: symbol of asset","raises":[{"type":"Exception","desc":"There is an error in the order process."}]},{"function":"sell(self, symbol, quantity, in_force, extended)","index":"sell","short_description":"Sells the specified asset.","long_description":"When called, a limit sell order is placed with a limit\\nprice 5% lower than the current price.","params":[{"name":"symbol","type":"str","desc":"Symbol of the asset to sell. ","default":"first symbol in watchlist","optional":true},{"name":"quantity","type":"float","desc":"Quantity of asset to sell ","default":"sells all","optional":true},{"name":"in_force","type":"str","desc":"Duration the order is in force. \'{gtc}\' or \'{gtd}\'. ","default":"\'gtc\'","optional":true},{"name":"extended","type":"str","desc":"Whether to trade in extended hours or not. ","default":"False","optional":true}],"returns":"A dictionary with the following keys:\\n- type: str, \'STOCK\' or \'CRYPTO\'\\n- id: str, ID of order\\n- symbol: str, symbol of asset","raises":[{"type":"Exception","desc":"There is an error in the order process."}]},{"function":"sell_option(self, symbol, quantity, in_force)","index":"sell_option","short_description":"Sells the specified option.","long_description":"When called, a limit sell order is placed with a limit\\nprice 5% lower than the current price.\\n\\nIf the option symbol is specified, it will sell that option. If it is not, then the\\nmethod will select the first stock symbol in the watchlist, and sell all options\\nrelated to that stock.","params":[{"name":"symbol","type":"str","desc":"Symbol of the asset to sell, in {OCC} format. ","default":"sell all options for the first stock in watchlist","optional":true},{"name":"quantity","type":"float","desc":"Quantity of asset to sell. ","default":"sells all","optional":true},{"name":"in_force","type":"str","desc":"Duration the order is in force. \'{gtc}\' or \'{gtd}\'. ","default":"\'gtc\'","optional":true}],"returns":"A dictionary with the following keys:\\n- type: \'OPTION\'\\n- id: ID of order\\n- symbol: symbol of asset","raises":[{"type":"Exception","desc":"There is an error in the order process."}]},{"function":"get_option_market_data(self, symbol)","index":"get_option_market_data","short_description":"Retrieves data of specified option.","long_description":null,"params":[{"name":"symbol","type":"str","desc":"{OCC} symbol of optio","default":null,"optional":true}],"returns":"A dictionary:\\n- price: price of option\\n- ask: ask price\\n- bid: bid price","raises":[]},{"function":"get_option_chain(self, symbol, date)","index":"get_option_chain","short_description":"Returns the option chain for the specified symbol and expiration date.","long_description":null,"params":[{"name":"symbol","type":"str","desc":"symbol of stoc","default":null,"optional":false},{"name":"date","type":"dt.datetime","desc":"date of option expiratio","default":null,"optional":false}],"returns":"A dataframe with the follwing columns:\\n    - exp_date(datetime.datetime): The expiration date\\n    - strike(float): Strike price\\n    - type(str): \'call\' or \'put\'\\n\\nThe index is the {OCC} symbol of the option.","raises":[]},{"function":"get_option_chain_info(self, symbol)","index":"get_option_chain_info","short_description":"Returns metadata about a stock\'s option chain","long_description":null,"params":[{"name":"symbol","type":"str","desc":"symbol of stock. ","default":"first symbol in watchlist","optional":true}],"returns":"A dict with the following keys:\\n- exp_dates: List of expiration dates, in the fomrat \\"YYYY-MM-DD\\"\\n- multiplier: Multiplier of the option, usually 100","raises":[]},{"function":"ema(self, symbol, period, interval, ref, prices)","index":"ema","short_description":"Calculate EMA","long_description":null,"params":[{"name":"symbol","type":"str","desc":"Symbol to perform calculation on. ","default":"first symbol in watchlist","optional":true},{"name":"period","type":"int","desc":"Period of EMA. ","default":"14","optional":true},{"name":"interval","type":"str","desc":"Interval to perform the calculation. ","default":"interval of algorithm","optional":true},{"name":"ref","type":"str","desc":"\'close\', \'open\', \'high\', or \'low\'. ","default":"\'close\'","optional":true},{"name":"prices","type":"list","desc":"When specified, this function will use the values provided in the\\nlist to perform calculations and ignore other parameters. ","default":"None","optional":true}],"returns":"A list in numpy format, containing EMA values","raises":[]},{"function":"rsi(self, symbol, period, interval, ref, prices)","index":"rsi","short_description":"Calculate RSI","long_description":null,"params":[{"name":"symbol","type":"str","desc":"Symbol to perform calculation on. ","default":"first symbol in watchlist","optional":true},{"name":"period","type":"int","desc":"Period of RSI. ","default":"14","optional":true},{"name":"interval","type":"str","desc":"Interval to perform the calculation. ","default":"interval of algorithm","optional":true},{"name":"ref","type":"str","desc":"\'close\', \'open\', \'high\', or \'low\'. ","default":"\'close\'","optional":true},{"name":"prices","type":"list","desc":"When specified, this function will use the values provided in the\\nlist to perform calculations and ignore other parameters. ","default":"None","optional":true}],"returns":"A list in numpy format, containing RSI values","raises":[]},{"function":"sma(self, symbol, period, interval, ref, prices)","index":"sma","short_description":"Calculate SMA","long_description":null,"params":[{"name":"symbol","type":"str","desc":"Symbol to perform calculation on. ","default":"first symbol in watchlist","optional":true},{"name":"period","type":"int","desc":"Period of SMA. ","default":"14","optional":true},{"name":"interval","type":"str","desc":"Interval to perform the calculation. ","default":"interval of algorithm","optional":true},{"name":"ref","type":"str","desc":"\'close\', \'open\', \'high\', or \'low\'. ","default":"\'close\'","optional":true},{"name":"prices","type":"list","desc":"When specified, this function will use the values provided in the\\nlist to perform calculations and ignore other parameters. ","default":"None","optional":true}],"returns":"A list in numpy format, containing SMA values","raises":[]},{"function":"bbands(self, symbol, period, interval, ref, dev, prices)","index":"bbands","short_description":"Calculate Bollinger Bands","long_description":null,"params":[{"name":"symbol","type":"str","desc":"Symbol to perform calculation on. ","default":"first symbol in watchlist","optional":true},{"name":"period","type":"int","desc":"Period of BBands. ","default":"14","optional":true},{"name":"interval","type":"str","desc":"Interval to perform the calculation. ","default":"interval of algorithm","optional":true},{"name":"ref","type":"str","desc":"\'close\', \'open\', \'high\', or \'low\'. ","default":"\'close\'","optional":true},{"name":"dev","type":"float","desc":"Standard deviation of the bands. ","default":"1.0","optional":true},{"name":"prices","type":"list","desc":"When specified, this function will use the values provided in the\\nlist to perform calculations and ignore other parameters. ","default":"None","optional":true}],"returns":"A tuple of numpy lists, each a list of BBand top, average, and bottom values","raises":[]},{"function":"get_account_buying_power(self)","index":"get_account_buying_power","short_description":"Returns the current buying power of the user","long_description":null,"params":[],"returns":"The current buying power as a float.","raises":[]},{"function":"get_account_equity(self)","index":"get_account_equity","short_description":"Returns the current equity.","long_description":null,"params":[],"returns":"The current equity as a float.","raises":[]},{"function":"get_asset_candle(self, symbol)","index":"get_asset_candle","short_description":"Returns the most recent candle as a pandas DataFrame","long_description":"This function is not compatible with options.","params":[{"name":"symbol","type":"str","desc":"Symbol of stock or crypto asset. ","default":"first symbol in watchlist","optional":true}],"returns":"Price of asset as a dataframe with the following columns:\\n    - open\\n    - high\\n    - low\\n    - close\\n    - volume\\n\\nThe index is a datetime object","raises":[{"type":"Exception","desc":"If symbol is not in the watchlist."}]},{"function":"get_asset_candle_list(self, symbol)","index":"get_asset_candle_list","short_description":"Returns the candles of an asset as a pandas DataFrame","long_description":"This function is not compatible with options.","params":[{"name":"symbol","type":"str","desc":"Symbol of stock or crypto asset. ","default":"first symbol in watchlist","optional":true}],"returns":"Prices of asset as a dataframe with the following columns:\\n    - open\\n    - high\\n    - low\\n    - close\\n    - volume\\n\\nThe index is a datetime object","raises":[{"type":"Exception","desc":"If symbol is not in the watchlist."}]},{"function":"get_asset_cost(self, symbol)","index":"get_asset_cost","short_description":"Returns the average cost of a specified asset.","long_description":null,"params":[{"name":"symbol","type":"str","desc":"Symbol of asset. ","default":"first symbol in watchlist","optional":true}],"returns":"Average cost of asset. Returns None if asset is not being tracked.","raises":[{"type":"Exception","desc":"If symbol is not currently owned."}]},{"function":"get_date(self)","index":"get_date","short_description":"Returns the current date.","long_description":null,"params":[],"returns":"The current date as a datetime object","raises":[]},{"function":"get_datetime(self)","index":"get_datetime","short_description":"Returns the current date and time.","long_description":"This returns the current time, which is different from the timestamp\\non a ticker. For example, if you are running an algorithm every 5 minutes,\\nat 11:30am you will get a ticker for 11:25am. This function will return\\n11:30am.","params":[],"returns":"The current date and time as a datetime object","raises":[]},{"function":"get_asset_price(self, symbol)","index":"get_asset_price","short_description":"Returns the current price of a specified asset.","long_description":null,"params":[{"name":"symbol","type":"str","desc":"Symbol of asset. ","default":"first symbol in watchlist","optional":true}],"returns":"Price of asset.","raises":[{"type":"Exception","desc":"If symbol is not in the watchlist."}]},{"function":"get_asset_price_list(self, symbol, interval, ref)","index":"get_asset_price_list","short_description":"Returns a list of recent prices for an asset.","long_description":"This function is not compatible with options.","params":[{"name":"symbol","type":"str","desc":"Symbol of stock or crypto asset. ","default":"first symbol in watchlist","optional":true},{"name":"interval","type":"str","desc":"Interval of data. ","default":"the interval of the algorithm","optional":true},{"name":"ref","type":"str","desc":"\'close\', \'open\', \'high\', or \'low\'. ","default":"\'close\'","optional":true}],"returns":"List of prices","raises":[]},{"function":"get_asset_quantity(self, symbol)","index":"get_asset_quantity","short_description":"Returns the quantity owned of a specified asset.","long_description":null,"params":[{"name":"symbol","type":"str","desc":"Symbol of asset. ","default":"first symbol in watchlist","optional":true}],"returns":"Quantity of asset as float. 0 if quantity is not owned.","raises":[{"type":null,"desc":""}]},{"function":"get_asset_returns(self, symbol)","index":"get_asset_returns","short_description":"Returns the return of a specified asset.","long_description":null,"params":[{"name":"symbol","type":"str","desc":"Symbol of stock, crypto, or option. Options should be in {OCC} format.\\n","default":"first symbol in watchlist","optional":true}],"returns":"Return of asset, expressed as a decimal.","raises":[]},{"function":"get_time(self)","index":"get_time","short_description":"Returns the current hour and minute.","long_description":"This returns the current time, which is different from the timestamp\\non a ticker. For example, if you are running an algorithm every 5 minutes,\\nat 11:30am you will get a ticker for 11:25am. This function will return\\n11:30am.","params":[],"returns":"The current time as a datetime object","raises":[]}]'),m=JSON.parse('[{"function":"start(self, interval, aggregations, sync)","index":"start","short_description":"Entry point to start the system.","long_description":null,"params":[{"name":"interval","type":"str","desc":"The interval to run the algorithm. ","default":"\'5MIN\'","optional":true},{"name":"aggregations","type":"list[str]","desc":"A list of intervals. The Trader will aggregate data to the intervals specified in this list.\\nFor example, if this is set to [\'5MIN\', \'30MIN\'], and interval is \'1MIN\', the algorithm will have access to\\n5MIN, 30MIN aggregated data in addition to 1MIN data. ","default":"None","optional":true},{"name":"sync","type":"bool","desc":"If true, the system will sync with the broker and fetch current positions and pending orders. ","default":"true","optional":true}],"returns":"","raises":[]},{"function":"set_symbol(self)","index":"set_symbol","short_description":"Specifies the symbol(s) to watch.","long_description":"Cryptocurrencies should be prepended with an `@` to differentiate them from stocks.\\nFor example, \'@ETH\' will refer to Etherium, while \'ETH\' will refer to Ethan Allen Interiors.\\nIf this method was previously called, the symbols specified earlier will be replaced with the\\nnew symbols.","params":[],"returns":"","raises":[]},{"function":"set_algo(self, algo)","index":"set_algo","short_description":"Specifies the algorithm to use.","long_description":null,"params":[{"name":"algo","type":"Algo","desc":"The algorithm to use. You can either pass in a single Algo class, or a\\nlist of Algo classes","default":null,"optional":false}],"returns":"","raises":[]}]'),y=JSON.parse('[{"function":"start(self, interval, aggregations, source, path)","index":"start","short_description":"Runs backtesting.","long_description":"The interface is very similar to the Trader class, with some additional parameters for specifying\\nbacktesting configurations.","params":[{"name":"interval","type":"str","desc":"The interval to run the algorithm on. ","default":"\'5MIN\'","optional":true},{"name":"aggregations","type":"List[str]","desc":"The aggregations to run. ","default":"[]","optional":true},{"name":"source","type":"str","desc":"The source of backtesting data.\\n\'FETCH\' will pull the latest data using the broker (if specified).\\n\'CSV\' will read data from a locally saved CSV file.\\n\'PICKLE\' will read data from a locally saved pickle file, generated using the Trader class.\\n","default":"\'PICKLE\'","optional":true},{"name":"path","type":"str","desc":"The path to the directory which backtesting data is stored.\\nThis parameter must be set accordingly if \'source\' is set to \'CSV\' or \'PICKLE\'. ","default":"\'./data\'","optional":true}],"returns":"","raises":[]}]');function g(e,t){var n;if("undefined"===typeof Symbol||null==e[Symbol.iterator]){if(Array.isArray(e)||(n=function(e,t){if(!e)return;if("string"===typeof e)return _(e,t);var n=Object.prototype.toString.call(e).slice(8,-1);"Object"===n&&e.constructor&&(n=e.constructor.name);if("Map"===n||"Set"===n)return Array.from(e);if("Arguments"===n||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n))return _(e,t)}(e))||t&&e&&"number"===typeof e.length){n&&(e=n);var r=0,s=function(){};return{s:s,n:function(){return r>=e.length?{done:!0}:{done:!1,value:e[r++]}},e:function(e){throw e},f:s}}throw new TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.")}var o,i=!0,a=!1;return{s:function(){n=e[Symbol.iterator]()},n:function(){var e=n.next();return i=e.done,e},e:function(e){a=!0,o=e},f:function(){try{i||null==n.return||n.return()}finally{if(a)throw o}}}}function _(e,t){(null==t||t>e.length)&&(t=e.length);for(var n=0,r=new Array(t);n<t;n++)r[n]=e[n];return r}function b(){var e,t=[],n=[],l=[],u=g(h);try{for(u.s();!(e=u.n()).done;){var f=e.value;t.push((0,r.jsx)(a.default,{dict:f}))}}catch(N){u.e(N)}finally{u.f()}var _,b=g(h);try{for(b.s();!(_=b.n()).done;){var v=_.value;t.push((0,r.jsx)(a.default,{dict:v}))}}catch(N){b.e(N)}finally{b.f()}var x,w=g(m);try{for(w.s();!(x=w.n()).done;){var j=x.value;n.push((0,r.jsx)(a.default,{dict:j}))}}catch(N){w.e(N)}finally{w.f()}var k,T=g(y);try{for(T.s();!(k=T.n()).done;){var S=k.value;l.push((0,r.jsx)(a.default,{dict:S}))}}catch(N){T.e(N)}finally{T.f()}return(0,r.jsxs)("div",{className:c().container,children:[(0,r.jsx)(o.default,{title:"Harvest | Documentation"}),(0,r.jsx)(s.default,{}),(0,r.jsxs)("main",{className:c().main,children:[(0,r.jsxs)("nav",{className:"".concat(d().nav," ").concat(p().card),children:[(0,r.jsx)("h3",{children:"Algo"}),(0,r.jsx)("h3",{children:"Trader"}),(0,r.jsx)("h3",{children:"BackTester"})]}),(0,r.jsxs)("section",{className:c().section,children:[(0,r.jsx)("h1",{children:"Documentation"}),(0,r.jsx)("h2",{className:d().className,children:"harvest.Algo"}),t,(0,r.jsx)("h2",{className:d().className,children:"harvest.Trader"}),n,(0,r.jsx)("h2",{className:d().className,children:"harvest.BackTester"}),l]})]}),(0,r.jsx)(i.default,{})]})}},4653:function(e,t,n){(window.__NEXT_P=window.__NEXT_P||[]).push(["/docs",function(){return n(2966)}])},4139:function(e){e.exports={nav:"Doc_nav__2GF3d",className:"Doc_className__38Gp3",entry:"Doc_entry__10WMz",paramHeader:"Doc_paramHeader__3-mXJ",paramReturn:"Doc_paramReturn__35Fxt",paramRaise:"Doc_paramRaise__3igaR",lookup:"Doc_lookup__1eTBB",raises:"Doc_raises__2IpAt"}},5016:function(e){e.exports={button:"rowcrop_button__1n6eZ",card:"rowcrop_card__25eqx",col4:"rowcrop_col4__2ZQay"}},3679:function(e){e.exports={container:"Home_container__3sao-",main:"Home_main__1Z1aG",nav:"Home_nav__2iapp",logo:"Home_logo__3GqVp",github:"Home_github__3XEl-",landing:"Home_landing__2U_o4",section:"Home_section__354aW",text:"Home_text__dq4ii",button:"Home_button__2hScn",col_card:"Home_col_card__6BIVE",col4:"Home_col4__2OXKu",footer:"Home_footer__2v49s"}},1664:function(e,t,n){e.exports=n(2167)}},function(e){e.O(0,[317,793,774,888,179],(function(){return t=4653,e(e.s=t);var t}));var t=e.O();_N_E=t}]);