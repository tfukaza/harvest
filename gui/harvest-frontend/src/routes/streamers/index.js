import { h, useState, useEffect } from 'preact';
import style from './style.css';

const items = ['A', 'B', 'C'];

const Streamers = () => (
	<div class={style.container}>
		<div class={style.horizantal_container}>
			<div>
				<div class={style.horizantal_container}>
					<h1>Streamers</h1>
					<button>ADD STREAMER</button>
				</div>
				<div>
					<ul>
						{items.map(result => (<li>{result}</li>))}
					</ul>
				</div>
			</div>
			<div>
				<div>
					<p>Streamer information</p>
				</div>
			</div>
		</div>
	</div>
);

export default Streamers;
