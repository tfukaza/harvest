(self.webpackChunk_N_E=self.webpackChunk_N_E||[]).push([[102],{1536:function(n,r,e){"use strict";e.r(r),e.d(r,{default:function(){return s}});var a=e(5893),t=e(7317);function s(n){var r=n.lang,e=n.value;return void 0===r&&(r="text"),void 0===e&&(e="Hello World"),(0,a.jsx)(t.Z,{language:r,customStyle:"",useInlineStyles:!1,children:e})}},3899:function(n,r,e){"use strict";e.r(r),e.d(r,{default:function(){return f}});var a=e(5893),t=e(4139),s=e.n(t),i=e(1536),l=JSON.parse('{"gtc":"Good-Til-Cancelled"}');function c(n,r){var e;if("undefined"===typeof Symbol||null==n[Symbol.iterator]){if(Array.isArray(n)||(e=function(n,r){if(!n)return;if("string"===typeof n)return o(n,r);var e=Object.prototype.toString.call(n).slice(8,-1);"Object"===e&&n.constructor&&(e=n.constructor.name);if("Map"===e||"Set"===e)return Array.from(n);if("Arguments"===e||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(e))return o(n,r)}(n))||r&&n&&"number"===typeof n.length){e&&(n=e);var a=0,t=function(){};return{s:t,n:function(){return a>=n.length?{done:!0}:{done:!1,value:n[a++]}},e:function(n){throw n},f:t}}throw new TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.")}var s,i=!0,l=!1;return{s:function(){e=n[Symbol.iterator]()},n:function(){var n=e.next();return i=n.done,n},e:function(n){l=!0,s=n},f:function(){try{i||null==e.return||e.return()}finally{if(l)throw s}}}}function o(n,r){(null==r||r>n.length)&&(r=n.length);for(var e=0,a=new Array(r);e<r;e++)a[e]=n[e];return a}function u(n){return n in l?l[n]:"404"}function f(n){var r=n.dict;if(void 0===r)return(0,a.jsx)("p",{children:":)"});var e=function(n){var r,e=[],t=c(n.params);try{for(t.s();!(r=t.n()).done;){var i=r.value,l=i.desc;void 0===l&&(l="");var o,f=/{[^{}]+}/g,d=l.match(f),h=l.split(f),p=[],m="",v=null,_=c(h);try{for(_.s();!(o=_.n()).done;){var y=o.value;p.push(y),null!==d&&d.length>0&&(m=d.shift().replace(/[{}]/g,""),v=(0,a.jsx)("span",{children:u(m)}),p.push((0,a.jsxs)("span",{className:s().lookup,children:[v,m]})))}}catch(x){_.e(x)}finally{_.f()}e.push((0,a.jsxs)("div",{children:[(0,a.jsxs)("p",{className:s().paramName,children:["\u2022 ",i.name]}),(0,a.jsxs)("p",{className:s().paramType,children:["\xa0(",i.type,"):"]}),(0,a.jsx)("p",{children:p}),(0,a.jsx)("p",{className:s().paramDef,children:i.default}),(0,a.jsx)("p",{children:d})]}))}}catch(x){t.e(x)}finally{t.f()}return e}(r),t=function(n){var r,e=[],t=c(n.raises);try{for(t.s();!(r=t.n()).done;){var s=r.value;e.push((0,a.jsxs)("li",{children:[(0,a.jsx)("span",{children:s.type+": "}),s.desc]}))}}catch(i){t.e(i)}finally{t.f()}return e}(r),l=function(n){var r,e=[],t=n.returns,s=t.match(/(\s*\n\s*- .+)+/g),i=c(t.split(/\s*- [^\n]*/).filter((function(n){return n.length>0})));try{for(i.s();!(r=i.n()).done;){var l=r.value;if(e.push((0,a.jsx)("p",{children:l})),null!==s&&s.length>0){var o,u=s.shift().match(/-.*[^\n]/g),f=[],d=c(u);try{for(d.s();!(o=d.n()).done;){var h=o.value;f.push((0,a.jsx)("li",{children:h.replace(/- /,"")}))}}catch(p){d.e(p)}finally{d.f()}e.push((0,a.jsx)("ul",{children:f}))}}}catch(p){i.e(p)}finally{i.f()}return e}(r);return(0,a.jsxs)("div",{className:s().entry,id:r.index,children:[(0,a.jsx)(i.default,{lang:"python",value:r.function}),(0,a.jsx)("p",{children:r.short_description}),(0,a.jsx)("p",{className:s().longDesc,children:r.long_description}),(0,a.jsxs)("div",{className:s().paramHeader,children:[(0,a.jsx)("h3",{children:"Params:"}),(0,a.jsx)("h4",{children:"Default"}),e]}),(0,a.jsxs)("div",{className:s().paramReturn,children:[(0,a.jsx)("h3",{children:"Returns:"}),l]}),(0,a.jsxs)("div",{className:s().paramRaise,children:[(0,a.jsx)("h3",{children:"Raises:"}),(0,a.jsx)("ul",{className:s().raises,children:t})]})]})}l.returns},6673:function(n,r,e){(window.__NEXT_P=window.__NEXT_P||[]).push(["/components/func",function(){return e(3899)}])},4139:function(n){n.exports={nav:"Doc_nav__2GF3d",className:"Doc_className__38Gp3",entry:"Doc_entry__10WMz",paramHeader:"Doc_paramHeader__3-mXJ",paramReturn:"Doc_paramReturn__35Fxt",paramRaise:"Doc_paramRaise__3igaR",lookup:"Doc_lookup__1eTBB",raises:"Doc_raises__2IpAt"}}},function(n){n.O(0,[317,774,888,179],(function(){return r=6673,n(n.s=r);var r}));var r=n.O();_N_E=r}]);