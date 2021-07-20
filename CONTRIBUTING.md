Interested in coding for Harvest? Awesome! 🤟 But before you begin, skim through the following sections:

# Principles
Keep the following core values of Harvest in mind, especially if you are coding a new feature or approving a big PR. 

- 😀 Beginner friendly: Keep the interface simple and minimal, focusing on the essentials. Complicated options and configurations should be hidden away. 
- 🛠️ Modifiable: The code should be easy for developers to add new features and make modifications. 
- 📜 Principle over performance: Sometimes you may have to choose between the performance of the code and following the principles. In such case, always choose the latter. 


# Testing
## Unit Testing
After any modifications to the code, conduct unit tests by running:
```bash
python -m unittest discover -s test
```
from the `harvest` directory. This will run the tests defined in the `test` directory.

## Real-Time Testing
Unit testing does not cover all possible situations Harvest might encounter. Whenever possible, run the program as if you are a user on your own machine to test the code in real-life environments. This is especially true for codes for specific brokerages, which automated unit tests cannot cover.   

**Make sure you don't accidentally `git push` secret keys of the brokerage you are using🤐**

## Website Testing
If you are working on the website, navigate to `harvest/website`, and run 
```bash
npm run dev
``` 
to start a hot-reloading dev server. If you think the website looks good, run 
```bash
npm run build && npm run export
``` 
to make sure the website can build without any problems. 

# Suggesting a Feature
Have an idea for a feature? Great! Take the following steps to make it part of Harvest:
1. Think through your idea, and ensure it follows the principles of Harvest.
2. [Submit a feature suggestion](https://github.com/tfukaza/harvest/issues/new?assignees=&labels=enhancement%2C+question&template=feature-request.md&title=%5B%F0%9F%92%A1Feature+Request%5D).
3. Ask people to around and see if they like your idea. **Merging new code requires the approval of at least 1 reviewer**, so you want as many people onboard with you as possible.
4. If people like your idea, begin writing your code 💻
5. Conduct tests as described in the Testing section.
6. Push your code, make a PR, and request review.
7. If your code is approved, congratulate yourself and hit the merge button.


