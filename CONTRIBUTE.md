Interested in coding for Harvest? Awesome! 🤟 But before you begin, skim through the following sections:

# Principles
Harvest puts a lot of emphasis on being user-friendly. If you are adding a new feature, modifying an existing one, or just making general enhancements, make sure it follows these principles:

- Beginner friendly: Keep the interface simple and minimal, focusing on the essentials. Complicated options and configurations should be hidden away. 
- Modifiable: The code should be easy for developers to add new features and make modifications. 
- Principle over performance: Sometimes you may have to choose between the performance of the code and following the principles. In such case, always choose the latter. 

These principles can manifest in many ways. For example, an early version of Harvest used a library that required building and installing binaries. Although this improved the performance of calculations, the setup process was confusing for those unfamiliar with computers. The library was eventually replaced with a pure-python alternative that was slightly slower but much easier to install. 

# Coding Process
To make the development process smoother for everyone, makes sure you follow these steps.

## Selecting an Issue

## Coding

## Testing

### Unit Test

### Real-time Testing

### Testing the Website

While generic tests are built into the CI/CD workflow, ideally you should conduct testing on your local working environment before pushing. This is especially true if you are working on a new feature, debugging, or making large modifications. 

Testing Harvest often requires you to save login credentials to access the brokers, so it is recommended that you test the code in a different directory than your working directory. 

For example, if you cloned this repo into `C:\Alice\document\harvest`, you can create a new directory `C:\Alice\document\testing`. All of your test codes and access credentials should then be stored in `testing` to ensure they don't accidentally get pushed to the public repo. You can run 
```
pip install ../harvest
``` 
from `testing` to install the latest codebase from your local machine.  

If you want to run the generic tests locally, run:
```
python -m unittest discover -s test
```
from the `harvest` directory.

The Harvest project has two websites: one for the Harvest homepage, and the other is the web interface to monitor Harvest.

The Harvest homepage is a pre-rendered NextJS/React website. Navigate to `harvest/website`, and run 
```
npm run dev
``` 
to start a hot-reloading dev server. If you think the website looks good, run 
```
npm run build && npm run export
``` 
to make sure the website can build without any problems. 

## Opening a PR 

## Maintaining 


