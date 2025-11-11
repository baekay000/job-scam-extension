new_set.csv is the new testing set that does not utilize the original fake job postings kaggle dataset, it is a mix of two separate datasets, as such I don't think it's the greatest but it seems to work ok

pare_post.csv may work better as the data is much more similar between the fake and real postings but it uses the original kaggle dataset so we shouldn't use this for finetuning testing, I just figured I'd include both though

model_test.py should run on the specified dataset and write the output to a .csv file
