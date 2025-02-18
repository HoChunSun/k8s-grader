#!/bin/bash

# Define variables
SSH_HOST=$(cat endpoint.txt | awk -F[/:] '{print $4}')
SSH_KEY="labsuser.pem"
SSH_USER="ec2-user"

ssh -o "StrictHostKeyChecking no" -i $SSH_KEY $SSH_USER@$SSH_HOST "kubectl proxy --address=0.0.0.0 --accept-hosts='.*'"
