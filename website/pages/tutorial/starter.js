import NavBar from '../components/navbar.js'
import Header from '../components/header.js'
import Footer from '../components/footer.js'
import CodeBlock from '../components/code.js'

import styles from '../../styles/Home.module.scss'

export default function Module() {
  return (
    <div className={styles.container}>
      <Header title="Harvest | Tutorials"></Header>
      <NavBar></NavBar>
      <main className={styles.main}>
        <section>

        </section>
        <section className={styles.section}>
            <div className={styles.text}> 
                <h1>Startup Guide</h1>
                <h2>Prerequisites</h2>
                <p>Before we begin, make sure you have the following:
                </p>
                <ul>
                    <li>Python, version 3.8 or higher.</li>
                    <li>A code editing software.</li>
                    <li>An account for a brokerage. In this tutorial we will be using Robinhood.</li>
                    <li>Basic coding skills. If you&#39;ve written anything more than 
                        &#39;Hello World&#39;, you should be good to go.
                    </li>
                </ul>
                

                <h2>Installing</h2>
                <p>First things first, let&#39;s install the library. </p>
                
                <CodeBlock lang="bash" value="pip install harvest-algo">
                </CodeBlock>
                
                <p>Next, we install additional libraries depending on which
                    broker you want to use. Harvest will do this automatically,
                    using the following command:
                </p>

                <CodeBlock lang="bash" value="pip install harvest-algo[BROKER]'">
                </CodeBlock>

                <p>
                Where BROKER is replaced by one of the following brokers supported by Harvest:
                </p>
                <ul>
                    <li>Robinhood</li>
                </ul>
                
                <h2>Example Code</h2>
                <p>
                Once you have everything installed, we are ready to begin writing the code.
                For this example we will use Robinhood, but the code is still mostly the same
                if you decide to use other brokers. 
                
                Before we begin, there are three components of Harvest you need to know:
                </p>
                <ul>
                    <li>Trader: The main module responsible for managing the other modules.</li>
                    <li>Broker: The module that communicates with the brokerage you are using.</li>
                    <li>Algo: The module where you define your algorithm.</li>
                </ul>
                <p>
                We begin coding by import the aforementioned components, 
                or &#39;modules&#39; as they are called in Python.
                </p>

                <CodeBlock
                    lang="python"
                    value={`from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.broker.robinhood import Robinhood`}>
                </CodeBlock>

                <p>Then we create a Trader, which will 
                    be the starting point of Harvest</p>

                <CodeBlock
                    lang="python"
                    value={`if __name__ == "__main__":
t = Trader( Robinhood() )`}>
                </CodeBlock>
                <p>
                Few things happen here, and don&#39;t worry, this is as complex as Harvest will get (for now).

                The trader class is instantiated. Traders take two Brokers as input, a streamer and a broker. streamer is the broker used to retrieve stock/cryto data. broker is the brokerage used to place orders and manage your portfolio.
                For this example, we initialize RobinhoodBroker. The broker automatically reads the credentials saved in secret.yaml and sets up a connection with the broker.
                The Robinhood broker is specified as a streamer and will be used to get stock/crypto data.
                If the broker is unspecified, Robinhood will also be used as a broker.
                Fortunately after this, things get pretty easy. We specify what stock to track, in this case Twitter (TWTR).
                </p>
                <CodeBlock
                    lang="python"
                    value={`t.set_symbol('TWTR')`}></CodeBlock>
                
                <p>At this point, we define our algorithm. Algorithms are created by extending the BaseAlgo class.
                </p>

                <CodeBlock
                    lang="python"
                    value={`class Twitter(BaseAlgo):
                    def setup(self):
                        pass

                    def main(self):
                        pass`}></CodeBlock>

                <p>every Algo must define two functions

                algo_init: Function called right before the algorithm starts
                handler: Function called at a specified interval.
                In this example, we create a simple algorithm that buys and sells a single stock.</p>
                <CodeBlock
                    lang="python"
                    value={`class Twitter(BaseAlgo):
    def setup(self):
        self.hold = False

    def main(self):
        if self.hold:
            self.sell('TWTR', 1)
            self.hold = False
        else:
            self.buy('TWTR', 1)
            self.hold = True`}></CodeBlock>
                
                <p>Finally, we tell the trader to use this algorithm, and run it. Below is the final code after putting everything together.</p>
                
                <CodeBlock
                    lang="python"
                    value={`from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.broker.robinhood import Robinhood

class Twitter(BaseAlgo):
    def setup(self):
        self.hold = False

    def main(self):
        if self.hold:
            self.sell('TWTR', 1)    
            self.hold = False
        else:
            self.buy('TWTR', 1)
            self.hold = True

if __name__ == "__main__":
    t = Trader( RobinhoodBroker())
    t.set_symbol('TWTR')
    t.set_algo(Twitter())
    t.run('1DAY')`}></CodeBlock>

                <p>By specifying interval=&#39;1DAY&#39; in run, the handler function will be called once every day.</p>

                <p>
                Now run the code. If this is the first time connecting to Robinhood, you should see 
                a setup wizard pop up. Follow the steps to set up login credentials for 
                Robinhood. 
                </p>
            </div>
         
        </section>
    </main>

    <Footer></Footer>
    </div>
  )
}
