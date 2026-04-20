DISTRO=$1
PASSWORD=$2

rm -f ${DISTRO}_reports/*

sshpass -p $PASSWORD scp -r ${DISTRO}@192.168.137.2:~/kubernetes-benchmark/cl2/reports/. ${DISTRO}_reports/

python3 ./format_data.py $DISTRO