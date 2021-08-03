import { h } from 'preact';
import { Router } from 'preact-router';

import Header from './header';

// Code-splitting is automated for `routes` directory
import Home from '../routes/home';
import Streamers from '../routes/streamers';
import Brokers from '../routes/brokers';
import Storages from '../routes/storages';
import Algorithms from '../routes/algorithms';
import Processes from '../routes/processes';

const App = () => (
	<div id="app">
		<Header />
		<Router>
			<Home path="/" />
			<Streamers path="/streamers" />
			<Brokers path="/brokers" />
			<Storages path="/storages" />
			<Algorithms path="/algorithms" />
			<Processes path="/processes" />
		</Router>
	</div>
)

export default App;
