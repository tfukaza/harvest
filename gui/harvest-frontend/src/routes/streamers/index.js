import { h, useState, useEffect, Component } from 'preact';

import Button from 'preact-material-components/Button';
import 'preact-material-components/Button/style.css';

import List from '../../components/list';

import style from './style.css';

class Streamers extends Component {

  constructor() {
    super();
    this.state = { 
    	streamers: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'],
    	active_streamer: null
    };
  }

  // Lifecycle: Called whenever our component is created
  componentDidMount() { }

  // Lifecycle: Called just before our component will be destroyed
  componentWillUnmount() { }

  showStreamer(streamer) {
  	this.setState({
  		active_streamer: streamer
  	});
  }

  showDialog() {

  }

  render(props, state) {
    return (
<div class={[style.container, style.full_display_height].join(' ')}>
	<div class={style.horizantal_container}>
		<div class={style.fourth_width}>
			<div class={style.horizantal_container}>
				<h1>Streamers</h1>
				<Button ripple raised primary>
          add streamer
        </Button>
			</div>
			<div class={style.half_display_height}>
				<List data={state.streamers} callBack={this.showStreamer.bind(this)} />
			</div>
		</div>
		<div class={[style.container, style.three_fourths_width].join(' ')}>
			<div>
				<p>Streamer information</p>
				{state.active_streamer ? (
					<p>The selected streamer is {state.active_streamer}</p>
				) : (
					<p>No Streamer selected</p>
				)}
			</div>
		</div>
	</div>
</div>
    	);
  }
}

export default Streamers;
