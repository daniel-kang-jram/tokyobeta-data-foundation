.PHONY: help init plan apply deploy-lambda test clean

# Default target
help:
	@echo "Tokyo Beta Data Consolidation - Make Commands"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make init          - Initialize Terraform backend"
	@echo "  make plan ENV=prod - Run terraform plan for environment"
	@echo "  make apply ENV=prod- Apply terraform changes"
	@echo ""
	@echo "Lambda:"
	@echo "  make deploy-lambda - Package and deploy Lambda function"
	@echo "  make test-lambda   - Test Lambda locally with sample dump"
	@echo ""
	@echo "Database:"
	@echo "  make init-db       - Create staging and analytics schemas"
	@echo "  make seed-geocoding- Load asset geocoding seed data"
	@echo ""
	@echo "Testing:"
	@echo "  make test          - Run all tests"
	@echo "  make validate      - Validate data after ETL"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean         - Remove build artifacts"

# Terraform operations
init:
	cd terraform/environments/prod && terraform init -backend-config="bucket=tokyobeta-terraform-state"

plan:
	@if [ -z "$(ENV)" ]; then echo "ERROR: ENV is required. Usage: make plan ENV=prod"; exit 1; fi
	cd terraform/environments/$(ENV) && terraform plan -out=tfplan

apply:
	@if [ -z "$(ENV)" ]; then echo "ERROR: ENV is required. Usage: make apply ENV=prod"; exit 1; fi
	cd terraform/environments/$(ENV) && terraform apply tfplan

# Lambda deployment
deploy-lambda:
	@echo "Packaging Lambda function..."
	cd lambda/etl_processor && \
		pip install -r requirements.txt -t ./package && \
		cd package && zip -r ../deployment_package.zip . && cd .. && \
		zip -g deployment_package.zip *.py && \
		zip -gr deployment_package.zip transformers/
	@echo "Deploying Lambda via Terraform..."
	cd terraform/environments/prod && terraform apply -target=module.lambda -auto-approve

test-lambda:
	cd scripts && python test_etl_local.py

# Database operations
init-db:
	cd scripts && ./init_db.sh

seed-geocoding:
	cd scripts && ./seed_geocoding.sh

# Testing
test:
	cd lambda/etl_processor && python -m pytest tests/

validate:
	cd scripts && python validate_data.py

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	cd lambda/etl_processor && rm -rf package deployment_package.zip
	cd terraform/environments/prod && rm -f tfplan
	cd terraform/environments/dev && rm -f tfplan
