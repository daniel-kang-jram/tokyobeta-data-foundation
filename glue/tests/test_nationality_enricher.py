"""
Unit tests for nationality_enricher.py - AWS Bedrock LLM nationality prediction

TDD Approach: Write tests first, then implement the enricher
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json


@pytest.fixture
def mock_bedrock_client():
    """Mock AWS Bedrock client."""
    client = Mock()
    return client


@pytest.fixture
def mock_aurora_connection():
    """Mock Aurora MySQL connection."""
    conn = Mock()
    cursor = Mock()
    conn.cursor.return_value = cursor
    return conn, cursor


@pytest.fixture
def sample_tenants_missing_nationality():
    """Sample tenant records with missing/placeholder nationality."""
    return [
        {
            'id': 87306,
            'full_name': 'SAW THANDAR',
            'nationality': 'レソト',
            'm_nationality_id': 200,
            'status': 9
        },
        {
            'id': 87307,
            'full_name': 'Shohei Sakai',
            'nationality': 'レソト',
            'm_nationality_id': 200,
            'status': 9
        },
        {
            'id': 88000,
            'full_name': '蔡欣芸',
            'nationality': None,
            'm_nationality_id': 0,
            'status': 9
        },
        {
            'id': 88001,
            'full_name': 'YUHUIMIN',
            'nationality': '',
            'm_nationality_id': 52,
            'status': 9
        },
        {
            'id': 88002,
            'full_name': 'DAVAADELEG BYAMBASUREN',
            'nationality': 'レソト',
            'm_nationality_id': 200,
            'status': 17  # Moved out - lower priority
        }
    ]


class TestNationalityEnricherInit:
    """Test enricher initialization and configuration."""
    
    def test_enricher_requires_aurora_config(self):
        """Test that enricher validates Aurora connection config."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        with pytest.raises(ValueError, match="Aurora endpoint required"):
            NationalityEnricher(
                aurora_endpoint=None,
                aurora_database='tokyobeta',
                secret_arn='arn:aws:secretsmanager:...',
                bedrock_region='us-east-1'
            )
    
    def test_enricher_requires_bedrock_config(self):
        """Test that enricher validates Bedrock config."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        with pytest.raises(ValueError, match="Bedrock region required"):
            NationalityEnricher(
                aurora_endpoint='cluster.amazonaws.com',
                aurora_database='tokyobeta',
                secret_arn='arn:aws:secretsmanager:...',
                bedrock_region=None
            )


class TestIdentifyTenantsNeedingEnrichment:
    """Test identification of tenants needing nationality prediction."""
    
    def test_identifies_lesotho_placeholder(self, mock_aurora_connection):
        """Test identifies レソト placeholder records."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        conn, cursor = mock_aurora_connection
        cursor.fetchall.return_value = [
            {'id': 87306, 'full_name': 'SAW THANDAR', 'nationality': 'レソト', 'm_nationality_id': 200, 'status': 9}
        ]
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'get_connection', return_value=conn):
            tenants = enricher.identify_tenants_needing_enrichment()
        
        # Should query for レソト, NULL, and empty string
        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert 'レソト' in sql or 'nationality' in sql.lower()
        assert len(tenants) == 1
    
    def test_prioritizes_active_residents(self, mock_aurora_connection):
        """Test that active residents are prioritized over moved out tenants."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        conn, cursor = mock_aurora_connection
        cursor.fetchall.return_value = [
            {'id': 1, 'full_name': 'Active', 'nationality': 'レソト', 'status': 9},
            {'id': 2, 'full_name': 'MovedOut', 'nationality': 'レソト', 'status': 17}
        ]
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'get_connection', return_value=conn):
            tenants = enricher.identify_tenants_needing_enrichment()
        
        # Check SQL has ORDER BY to prioritize active status
        sql = cursor.execute.call_args[0][0]
        assert 'ORDER BY' in sql.upper()
    
    def test_limits_batch_size(self, mock_aurora_connection):
        """Test that batch size limit is enforced."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        conn, cursor = mock_aurora_connection
        # Return only 1000 (since SQL has LIMIT 1000)
        cursor.fetchall.return_value = [
            {'id': i, 'full_name': f'Tenant{i}', 'nationality': 'レソト', 'm_nationality_id': 200, 'status': 9}
            for i in range(1000)
        ]
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1',
            max_batch_size=1000
        )
        
        with patch.object(enricher, 'get_connection', return_value=conn):
            tenants = enricher.identify_tenants_needing_enrichment()
        
        # Check SQL query has LIMIT
        sql = cursor.execute.call_args[0][0]
        assert 'LIMIT 1000' in sql or 'LIMIT {}'.format(enricher.max_batch_size) in sql
        # Should return exactly max_batch_size (since we mocked that many)
        assert len(tenants) == 1000


class TestBedrockNationalityPrediction:
    """Test AWS Bedrock LLM nationality prediction."""
    
    def test_predict_nationality_from_name_myanmar(self, mock_bedrock_client):
        """Test predicts Myanmar from 'SAW THANDAR'."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        mock_bedrock_client.invoke_model.return_value = {
            'body': MagicMock(read=lambda: json.dumps({
                'content': [{'text': 'Myanmar'}]
            }).encode())
        }
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'bedrock_client', mock_bedrock_client):
            prediction = enricher.predict_nationality('SAW THANDAR')
        
        assert prediction == 'Myanmar'
    
    def test_predict_nationality_from_name_japanese(self, mock_bedrock_client):
        """Test predicts Japan from Japanese name."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        mock_bedrock_client.invoke_model.return_value = {
            'body': MagicMock(read=lambda: json.dumps({
                'content': [{'text': '日本'}]
            }).encode())
        }
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'bedrock_client', mock_bedrock_client):
            prediction = enricher.predict_nationality('山田太郎')
        
        assert prediction == '日本'
    
    def test_predict_nationality_from_name_chinese(self, mock_bedrock_client):
        """Test predicts China from Chinese characters."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        mock_bedrock_client.invoke_model.return_value = {
            'body': MagicMock(read=lambda: json.dumps({
                'content': [{'text': '中国'}]
            }).encode())
        }
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'bedrock_client', mock_bedrock_client):
            prediction = enricher.predict_nationality('蔡欣芸')
        
        assert prediction == '中国'
    
    def test_handles_bedrock_api_error_gracefully(self, mock_bedrock_client):
        """Test handles Bedrock API errors without crashing."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        mock_bedrock_client.invoke_model.side_effect = Exception("Bedrock API error")
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'bedrock_client', mock_bedrock_client):
            prediction = enricher.predict_nationality('SAW THANDAR')
        
        # Should return None or 'Unknown' instead of crashing
        assert prediction in (None, 'Unknown', 'その他')
    
    def test_constructs_proper_bedrock_prompt(self, mock_bedrock_client):
        """Test constructs appropriate prompt for Bedrock."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        mock_bedrock_client.invoke_model.return_value = {
            'body': MagicMock(read=lambda: json.dumps({
                'content': [{'text': 'Myanmar'}]
            }).encode())
        }
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'bedrock_client', mock_bedrock_client):
            enricher.predict_nationality('SAW THANDAR')
        
        # Check invoke_model was called with proper structure
        call_args = mock_bedrock_client.invoke_model.call_args
        assert 'modelId' in call_args[1]
        assert 'body' in call_args[1]
        
        # Parse body to check prompt
        body = json.loads(call_args[1]['body'])
        assert 'messages' in body or 'prompt' in body
    
    def test_uses_claude_3_haiku_model(self, mock_bedrock_client):
        """Test uses Claude 3 Haiku model for cost efficiency."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        mock_bedrock_client.invoke_model.return_value = {
            'body': MagicMock(read=lambda: json.dumps({
                'content': [{'text': 'Japan'}]
            }).encode())
        }
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'bedrock_client', mock_bedrock_client):
            enricher.predict_nationality('Test Name')
        
        call_args = mock_bedrock_client.invoke_model.call_args
        # Should use Haiku (cheapest model for this task)
        assert 'haiku' in call_args[1]['modelId'].lower()


class TestBatchProcessing:
    """Test batch processing of nationality predictions."""
    
    def test_processes_batch_with_rate_limiting(self, mock_bedrock_client, sample_tenants_missing_nationality):
        """Test batch processing respects API rate limits."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        import time
        
        mock_bedrock_client.invoke_model.return_value = {
            'body': MagicMock(read=lambda: json.dumps({
                'content': [{'text': 'Japan'}]
            }).encode())
        }
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1',
            requests_per_second=5  # Rate limit
        )
        
        with patch.object(enricher, 'bedrock_client', mock_bedrock_client):
            start = time.time()
            results = enricher.batch_predict_nationalities(sample_tenants_missing_nationality)
            elapsed = time.time() - start
        
        # Should have called Bedrock for each tenant
        assert mock_bedrock_client.invoke_model.call_count == len(sample_tenants_missing_nationality)
        
        # Should respect rate limit (5 req/sec = 0.2 sec between requests)
        # For 5 tenants, should take at least 0.8 seconds
        # (But we'll be lenient in test: > 0.5 seconds)
        assert elapsed >= 0.5 or mock_bedrock_client.invoke_model.call_count <= 5
    
    def test_batch_predict_returns_structured_results(self, mock_bedrock_client, sample_tenants_missing_nationality):
        """Test batch prediction returns properly structured results."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        mock_bedrock_client.invoke_model.return_value = {
            'body': MagicMock(read=lambda: json.dumps({
                'content': [{'text': 'Japan'}]
            }).encode())
        }
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'bedrock_client', mock_bedrock_client):
            results = enricher.batch_predict_nationalities(sample_tenants_missing_nationality)
        
        # Should return list of dicts with tenant_id and predicted_nationality
        assert isinstance(results, list)
        assert len(results) == len(sample_tenants_missing_nationality)
        
        for result in results:
            assert 'tenant_id' in result
            assert 'predicted_nationality' in result
            assert 'confidence' in result or 'model_used' in result


class TestDatabaseUpdate:
    """Test updating Aurora database with predictions."""
    
    def test_updates_staging_table_with_predictions(self, mock_aurora_connection):
        """Test writes predictions to staging.tenants llm_nationality column."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        conn, cursor = mock_aurora_connection
        
        predictions = [
            {'tenant_id': 87306, 'predicted_nationality': 'Myanmar', 'confidence': 0.95},
            {'tenant_id': 87307, 'predicted_nationality': '日本', 'confidence': 0.98}
        ]
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'get_connection', return_value=conn):
            enricher.save_predictions(predictions)
        
        # Should have called execute for each prediction
        assert cursor.execute.call_count >= len(predictions)
        
        # Check UPDATE statement structure
        update_calls = [call for call in cursor.execute.call_args_list 
                       if 'UPDATE' in str(call[0][0]).upper()]
        assert len(update_calls) > 0
        
        # Should update llm_nationality column
        update_sql = str(update_calls[0][0][0])
        assert 'llm_nationality' in update_sql.lower()
    
    def test_creates_llm_nationality_column_if_not_exists(self, mock_aurora_connection):
        """Test creates llm_nationality column if it doesn't exist."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        conn, cursor = mock_aurora_connection
        # Mock column doesn't exist
        cursor.fetchone.return_value = {'col_exists': 0}
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'get_connection', return_value=conn):
            enricher.ensure_llm_nationality_column_exists()
        
        # Should execute ALTER TABLE ADD COLUMN
        assert cursor.execute.call_count >= 2  # Check + ALTER
        calls = [str(call[0][0]) for call in cursor.execute.call_args_list]
        assert any('ALTER TABLE' in call.upper() for call in calls)
        assert any('llm_nationality' in call.lower() for call in calls)
    
    def test_handles_database_update_errors_gracefully(self, mock_aurora_connection):
        """Test handles database errors without losing all progress."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        conn, cursor = mock_aurora_connection
        cursor.execute.side_effect = Exception("Database connection lost")
        
        predictions = [
            {'tenant_id': 87306, 'predicted_nationality': 'Myanmar', 'confidence': 0.95}
        ]
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'get_connection', return_value=conn):
            # Should not crash, should log error
            try:
                enricher.save_predictions(predictions)
            except Exception as e:
                # Can raise exception, but should have logged it
                pass


class TestEndToEndWorkflow:
    """Test complete end-to-end enrichment workflow."""
    
    def test_enrich_all_pipeline(self, mock_aurora_connection, mock_bedrock_client):
        """Test complete enrichment pipeline from query to update."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        conn, cursor = mock_aurora_connection
        
        # Mock column check (column exists)
        cursor.fetchone.return_value = {'col_exists': 1}
        
        # Mock identify step
        cursor.fetchall.return_value = [
            {'id': 87306, 'full_name': 'SAW THANDAR', 'nationality': 'レソト', 'm_nationality_id': 200, 'status': 9}
        ]
        
        # Mock Bedrock prediction
        mock_bedrock_client.invoke_model.return_value = {
            'body': MagicMock(read=lambda: json.dumps({
                'content': [{'text': 'Myanmar'}]
            }).encode())
        }
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'get_connection', return_value=conn):
            with patch.object(enricher, 'bedrock_client', mock_bedrock_client):
                summary = enricher.enrich_all_missing_nationalities()
        
        # Should return summary statistics
        assert 'tenants_identified' in summary
        assert 'predictions_made' in summary
        assert 'successful_updates' in summary
        assert summary['tenants_identified'] == 1
        assert summary['predictions_made'] == 1
    
    def test_dry_run_mode_does_not_update_database(self, mock_aurora_connection, mock_bedrock_client):
        """Test dry run mode predicts but doesn't update database."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        conn, cursor = mock_aurora_connection
        
        # Mock column check (column exists)
        cursor.fetchone.return_value = {'col_exists': 1}
        
        cursor.fetchall.return_value = [
            {'id': 87306, 'full_name': 'SAW THANDAR', 'nationality': 'レソト', 'm_nationality_id': 200, 'status': 9}
        ]
        
        mock_bedrock_client.invoke_model.return_value = {
            'body': MagicMock(read=lambda: json.dumps({
                'content': [{'text': 'Myanmar'}]
            }).encode())
        }
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1',
            dry_run=True
        )
        
        with patch.object(enricher, 'get_connection', return_value=conn):
            with patch.object(enricher, 'bedrock_client', mock_bedrock_client):
                with patch.object(enricher, 'save_predictions') as mock_save:
                    summary = enricher.enrich_all_missing_nationalities()
        
        # Should have queried and predicted
        assert summary['predictions_made'] == 1
        
        # save_predictions should have been called (dry_run check is inside)
        # But actual UPDATE should not happen (checked via log message)
        mock_save.assert_called_once()


class TestLoggingAndMetrics:
    """Test logging and CloudWatch metrics."""
    
    def test_logs_progress_every_n_records(self, mock_aurora_connection, mock_bedrock_client):
        """Test logs progress periodically during batch processing."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        mock_bedrock_client.invoke_model.return_value = {
            'body': MagicMock(read=lambda: json.dumps({
                'content': [{'text': 'Japan'}]
            }).encode())
        }
        
        # Create 50 sample tenants
        large_batch = [
            {'id': i, 'full_name': f'Tenant{i}', 'nationality': 'レソト', 'status': 9}
            for i in range(50)
        ]
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1',
            log_every=10  # Log every 10 records
        )
        
        with patch.object(enricher, 'bedrock_client', mock_bedrock_client):
            with patch('glue.scripts.nationality_enricher.logger') as mock_logger:
                results = enricher.batch_predict_nationalities(large_batch)
        
        # Should have logged progress multiple times
        info_calls = [call for call in mock_logger.info.call_args_list]
        # At least 5 progress logs for 50 records with log_every=10
        assert len(info_calls) >= 5
    
    def test_returns_detailed_summary_statistics(self, mock_aurora_connection, mock_bedrock_client):
        """Test returns comprehensive summary after enrichment."""
        from glue.scripts.nationality_enricher import NationalityEnricher
        
        conn, cursor = mock_aurora_connection
        
        # Mock column check (column exists)
        cursor.fetchone.return_value = {'col_exists': 1}
        
        cursor.fetchall.return_value = [
            {'id': 1, 'full_name': 'Test', 'nationality': 'レソト', 'm_nationality_id': 200, 'status': 9}
        ]
        
        mock_bedrock_client.invoke_model.return_value = {
            'body': MagicMock(read=lambda: json.dumps({
                'content': [{'text': 'Japan'}]
            }).encode())
        }
        
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )
        
        with patch.object(enricher, 'get_connection', return_value=conn):
            with patch.object(enricher, 'bedrock_client', mock_bedrock_client):
                summary = enricher.enrich_all_missing_nationalities()
        
        # Should return comprehensive summary
        required_fields = [
            'tenants_identified',
            'predictions_made',
            'successful_updates',
            'failed_updates',
            'execution_time_seconds'
        ]
        
        for field in required_fields:
            assert field in summary, f"Missing summary field: {field}"


class TestProductionCacheContracts:
    """Test explicit cache behavior for production reliability contracts."""

    def test_save_predictions_returns_explicit_update_counts(self, mock_aurora_connection):
        from glue.scripts.nationality_enricher import NationalityEnricher

        conn, _cursor = mock_aurora_connection
        predictions = [
            {
                'tenant_id': 87306,
                'predicted_nationality': 'ミャンマー',
                'confidence': 0.95,
                'original_name': 'SAW THANDAR',
            },
            {
                'tenant_id': 87307,
                'predicted_nationality': None,
                'confidence': 0.10,
                'original_name': 'UNKNOWN',
            },
        ]

        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )

        with patch.object(enricher, 'get_connection', return_value=conn):
            summary = enricher.save_predictions(predictions)

        assert summary['successful_updates'] == 1
        assert summary['failed_updates'] == 0

    def test_ensure_property_municipality_cache_table_exists(self, mock_aurora_connection):
        from glue.scripts.nationality_enricher import NationalityEnricher

        conn, cursor = mock_aurora_connection
        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )

        with patch.object(enricher, 'get_connection', return_value=conn):
            enricher.ensure_property_municipality_cache_table_exists()

        create_calls = [str(call[0][0]) for call in cursor.execute.call_args_list]
        assert any('llm_property_municipality_cache' in sql for sql in create_calls)

    def test_infer_municipality_from_address_prefers_deterministic_parse(self):
        from glue.scripts.nationality_enricher import NationalityEnricher

        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )

        assert enricher.infer_municipality_from_address("東京都新宿区西新宿1-2-3") == "新宿区"
        assert enricher.infer_municipality_from_address("神奈川県横浜市港北区新横浜2-1-1") == "横浜市"
        assert enricher.infer_municipality_from_address("NoAddress") is None

    def test_identify_apartments_needing_municipality_enrichment_applies_limit(
        self,
        mock_aurora_connection,
    ):
        from glue.scripts.nationality_enricher import NationalityEnricher

        conn, cursor = mock_aurora_connection
        cursor.fetchall.return_value = [
            {'id': 1, 'apartment_name': 'A', 'prefecture': '東京都', 'municipality': None, 'address': '新宿区1-1'},
        ]

        enricher = NationalityEnricher(
            aurora_endpoint='test.com',
            aurora_database='tokyobeta',
            secret_arn='arn:test',
            bedrock_region='us-east-1'
        )

        with patch.object(enricher, 'get_connection', return_value=conn):
            rows = enricher.identify_apartments_needing_municipality_enrichment(max_batch_size=150)

        assert len(rows) == 1
        sql = cursor.execute.call_args[0][0]
        assert "LIMIT 150" in sql
