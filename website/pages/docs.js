import NavBar from './components/navbar.js'
import Header from './components/header.js'
import Footer from './components/footer.js'
import Function from './components/func.js'
import Link from 'next/link'

import styles from '../styles/Home.module.scss'
import doc from '../styles/Doc.module.css'
import rc from '../styles/rowcrop.module.css'

import algos from './docs-content/BaseAlgo.json'
import trader from './docs-content/Trader.json'
import backtester from './docs-content/BackTester.json'

export default function Home() {
  let algo_items = [];
  let trader_items = [];
  let backtester_items = [];
  // let algo_func = [];
  for (let val of algos){
    algo_items.push(<Function dict={val}></Function>);
    // algo_func.push(<Link 
    //                 href={'/docs#'+val["index"]}
    //                 passHref>
    //                   <li>{val["index"]}</li></Link>)
  }
  for (let val of algos){
    algo_items.push(<Function dict={val}></Function>);
  }
  for (let val of trader){
    trader_items.push(<Function dict={val}></Function>);
  }
  for (let val of backtester){
    backtester_items.push(<Function dict={val}></Function>);
  }

  return (
    <div className={styles.container}>
      <Header title="Harvest | Documentation"></Header>
      <NavBar></NavBar>      
      <main className={styles.main}>
          <nav className={`${doc.nav} ${rc.card}`}>
            <h3>Algo</h3>
            <h3>Trader</h3>
            <h3>BackTester</h3>
          </nav>
        <section className={styles.section}>
          <h1>Documentation</h1>
          <h2 className={doc.className}>harvest.Algo</h2>
          {algo_items}
          <h2 className={doc.className}>harvest.Trader</h2>
          {trader_items}
          <h2 className={doc.className}>harvest.BackTester</h2>
          {backtester_items}
        </section>
      </main>

      <Footer></Footer>
    </div>
  )
}
