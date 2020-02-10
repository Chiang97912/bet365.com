#
# created by Peter at 2019/7/10
#

# echo "=============================="
# echo "====removing useless files===="
# echo "=============================="

# rm -rf .git
# rm *~
# rm *.log
# rm *.aux
# rm *.out

# echo "================================"
# echo "==reinitialize git repository==="
# echo "================================"

# git init
# git remote add origin git@github.com:Chiang97912/bet365.com.git

echo "=============================="
echo "======committing changes======"
echo "=============================="

git add *
git add .gitignore
git stage *
git commit -am "$(date "+%Y-%m-%d %H:%M:%S")" >> commit.log
git gc >> git-gc.log

echo "=============================="
echo "=====pushing, please wait====="
echo "=============================="

git push --force origin HEAD
git status

echo "=============================="
echo "========all tasks done========"
echo "=============================="

rm *.log
