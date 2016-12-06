#!/bin/bash

#
# Furpose: Script calls a number of HBASE shell scripts and pipes their 
# output into hbase shell for execution. 
#
# SET THE FOLLOWING VALUES:
#
# path=
# hbase_bin=
# current_file=
# target_file=
#


# Validate that current and target files are not empty
##### TODO validate the version has the right format
##### REGEX check: ^[0-9]-[0-9]-[0-9]

function dir_2_number {
  echo $1 | tr '-' ' ' | awk '{ printf "%02d%02d%02d", $1 ,$2, $3 }'
}

current=`cat $current_file`
cur=$(dir_2_number $current)
target=`cat $target_file`
tar=$(dir_2_number $target)
if [ -z "$current" ]; then
  echo "Missing current version in $current_file. Setting HBase current version to 0-3-0."
  echo "0-3-0" > $current_file
  current="0-3-0"
  cur="000300"
fi
if [ -z "$target" ]; then
  echo  "Missing target version in $target_file."
  exit 2;
fi

echo "Running HBase scripts from current version:$current to target version:$target."
summary=$'\n'"HBase migration scripts summary"$'\n'
summary+="$msg"$'\n'"List of scripts:"
echo "$msg"

cd $path;
for dir in `ls -dv */ | tr -d '/'`; do
  d=$(dir_2_number $dir)
  if [ "$d" -ge "$cur" ] && [ "$d" -le "$tar" ]; then
    success=true
    # First run all the FORWARD scripts inside a specific version
    for f in `ls -v $dir/*-FORWARD.sh 2> /dev/null`; do
      echo "------------------------------------------------------------------"
      echo "Script to be run: $f";
      echo "sh $f | $hbase_bin shell;";
      summary+=$'\n\t'"$f";
      answer=$(sh $f | $hbase_bin shell;)
      echo $answer

      if [[ $(echo $answer | grep -o 'ERROR') ]]; then
        echo $summary
        echo "***** ERROR FOUND IN HBASE OUTPUT, EXITING *****"
        exit 2
      else
        echo "***** NO ERRORS, CONTINUING *****"
      fi
    done

    # Second run all the VERIFY scripts inside a specific version
    for f in `ls $dir/*-VERIFY.sh 2> /dev/null`; do
      echo "------------------------------------------------------------------"
      echo "Script to be run: $f";
      echo "sh $f | $hbase_bin shell;";
      answer=$(sh $f $hbase_bin;);
      echo $answer;
      # Check the script's response
      resp=`echo "$answer" | grep response`
      if [ -z "$resp" ]; then
        success=false
        echo "****  ERROR  ****  The output does not contain a response field."
        summary+=$'\n\t'"$f  ::  *** NO RESPONSE ***";
      else
        resp=`echo "$resp" | tr -d ' {}' | awk -F',' '{print $1}' | awk -F':' '{print $2}'`
        if [ $resp != true ]; then
          success=false
        fi
        summary+=$'\n\t'"$f  ::  $resp";
      fi
    done

    # Validate that all the migration scripts were run successfully and then update the current version
    if [ $success == true ]; then
      echo "${dir}" > $current_file
      msg="SUCCESS - Updating HBase current version to $dir."
      echo $'\n'"$msg"$'\n'
      summary+=$'\n\t'"$msg";
    else
      msg="***** FAILURE ***** - HBase migration scripts failed. Aborting."
      echo $'\n'$'\n'"$msg"$'\n'$'\n'
      summary+=$'\n'$'\n'"$msg";
      echo "$summary"
      exit 2;
    fi
  fi
done

echo "$summary"

