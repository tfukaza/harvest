import { h } from 'preact';
import style from './style.css';

const Home = () => (
	<div class={style.container}>
		<div class={style.description}>
			<p>Harvest is a tool to aid you in algorithmic trading. While you can use Harvest as a python package its also available as a local server.</p>
			<br />
			<p>The flow for using Harvest as a local server is to first define your streamer. This is how you will get your stock / crypto data. Then you will create a broker which will be used to handle buying and selling stocks and cryptos. After that you can specify a storage method. This is how Harvest will store stock and crypto data persistantly. The next step is the fun part. In the Algo section you will write code that will take in stock and/or cypto data, preform analysis and decide whether to buy, sell, or hold your stocks. Finally, once you have completed all of these, you can create a process. A process uses the streamer, broker, storage, and algorithm you created and runs you algorithm. Processes can be started, paused, and terminated at anytime you like. You can have as many processes as you want. Additionally, processes let you know how well its doing by frequently updating information such as equity, etc.</p>
		</div>
	</div>
);

export default Home;
