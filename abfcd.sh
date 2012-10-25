abfcd()
{
  if [ $2 ] || [ -z $1 ] ; then
    echo "Syntax: abfcd [group/]project"
    return 1
  fi
  output=`abf locate -p $1`
  if [[ $output == error* ]] || [[ -z $output ]] ; then
    echo $output;
    return;
  fi

  cd $output
}
