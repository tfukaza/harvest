import { h } from 'preact';
import { Link } from 'preact-router/match';
import style from './style.css';

const Header = () => (
	<header class={style.header}>
		<nav>
			<Link class={style.home} activeClassName={style.active} href="/">Harvest</Link>
			<Link activeClassName={style.active} href="/streamers">Steamers</Link>
			<Link activeClassName={style.active} href="/brokers/">Brokers</Link>
			<Link activeClassName={style.active} href="/storages/">Storages</Link>
			<Link activeClassName={style.active} href="/algorithms/">Algos</Link>
			<Link activeClassName={style.active} href="/processes/">Processes</Link>
		</nav>
	</header>
);

export default Header;
