import { h, Component } from 'preact';
import style from './style.css';

class List extends Component {

  constructor(props) {
    super(props);
    this.state = { }
  }

  render(props, state) {
    return (
<ul class={style.list}>
    {props.data.map(item => <li onClick={() => props.callBack(item) }>{item}</li>)}
</ul>
        );
  }
}

export default List;
