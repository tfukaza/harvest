# Motivation
If you look around, you'll notice that there are already countless algo-trading frameworks out there. So why do we need another one? That's because many of the existing frameworks have one or more of the following issues:
- Requires users to pay for certain features.
- The code is closed source, and cannot be modified by the community.
- The interface is complex, and the learning curve is steep.
- Only supports specific brokerages.
- Only works for specific type of assets, like cryptocurrencies. 

The goal of Harvest is therefore:
- Be free and open source.
- Allow users and dev to mod the framework as they need. 
- Keep the functionality minimal yet flexible and robust. 
- Support many popular brokerages.
- Support stocks, crypto, and options.

# Principles
The following are the core values of this project you should keep in mind, especially if you are coding a new feature or approving a big PR. 

- 😀 Beginner friendly: Keep the interface simple and minimal, focusing on the essentials. Complicated options and configurations should be hidden away. 
- 🛠️ Modifiable: The code should be easy for developers to add new features and make modifications. 
- 📜 Principle over performance: Sometimes you may have to choose between the performance of the code and following the principles. In such case, always choose the latter. 


# Testing
## Unit Testing
After any modifications to the code, conduct unit tests by running:
```bash
python -m unittest discover -s tests
```
from the project's root directory. This will run the tests defined in the `tests` directory.

## Real-Time Testing
Unit testing does not cover all possible situations Harvest might encounter. Whenever possible, run the program as if you are a user on your own machine to test the code in real-life environments. This is especially true for codes for specific brokerages, which automated unit tests cannot cover.   

**Make sure you don't accidentally `git push` secret keys of the brokerage you are using🤐**

## Website Testing
If you are working on the website, navigate to `/website`, and run 
```bash
npm run dev
``` 
to start a hot-reloading dev server. If you think the website looks good, run 
```bash
npm run build && npm run export
``` 
to make sure the website can build without any problems. 


