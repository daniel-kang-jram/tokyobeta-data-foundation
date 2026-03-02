#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const malformedMetadataPathPattern = /\/api\/\/+[^"'\s>]*evidencemeta\.json/g;

/**
 * @param {string[]} argv
 * @returns {{ buildDir: string, routes: string[] }}
 */
function parseArgs(argv) {
	let buildDir = 'evidence/build';
	/** @type {string[]} */
	let routes = [];

	for (let i = 0; i < argv.length; i += 1) {
		const arg = argv[i];

		if (arg === '--build-dir') {
			buildDir = argv[i + 1] ?? '';
			i += 1;
			continue;
		}

		if (arg === '--routes') {
			i += 1;
			while (i < argv.length && !argv[i].startsWith('--')) {
				routes.push(argv[i]);
				i += 1;
			}
			i -= 1;
			continue;
		}

		throw new Error(`Unknown argument: ${arg}`);
	}

	if (!buildDir) {
		throw new Error('Missing value for --build-dir');
	}

	if (routes.length === 0) {
		throw new Error('At least one route is required via --routes');
	}

	return { buildDir, routes };
}

/**
 * @param {string} filePath
 * @param {string[]} errors
 * @returns {string | null}
 */
function readHtml(filePath, errors) {
	if (!fs.existsSync(filePath)) {
		errors.push(`Missing route page: ${filePath}`);
		return null;
	}

	return fs.readFileSync(filePath, 'utf-8');
}

try {
	const { buildDir, routes } = parseArgs(process.argv.slice(2));
	const resolvedBuildDir = path.resolve(buildDir);
	/** @type {string[]} */
	const errors = [];

	/** @type {Array<{ label: string, filePath: string, expectedMetaPath: string }>} */
	const routeContracts = [
		{
			label: '/',
			filePath: path.join(resolvedBuildDir, 'index.html'),
			expectedMetaPath: '/api/evidencemeta.json'
		},
		...routes.map((route) => ({
			label: route,
			filePath: path.join(resolvedBuildDir, route, 'index.html'),
			expectedMetaPath: `/api/${route}/evidencemeta.json`
		}))
	];

	for (const contract of routeContracts) {
		const html = readHtml(contract.filePath, errors);
		if (html === null) {
			continue;
		}

		if (malformedMetadataPathPattern.test(html)) {
			errors.push(
				`Malformed metadata API path found in ${contract.filePath} (contains /api//.../evidencemeta.json)`
			);
		}
		malformedMetadataPathPattern.lastIndex = 0;

		if (!html.includes(contract.expectedMetaPath)) {
			errors.push(
				`Missing expected metadata reference "${contract.expectedMetaPath}" in ${contract.filePath}`
			);
		}
	}

	if (errors.length > 0) {
		console.error('Route contract verification failed:');
		for (const error of errors) {
			console.error(`- ${error}`);
		}
		process.exit(1);
	}

	console.log(
		`Route contract verification passed for ${routeContracts.length} pages in ${resolvedBuildDir}.`
	);
} catch (error) {
	const message = error instanceof Error ? error.message : String(error);
	console.error(`Route contract verification error: ${message}`);
	process.exit(1);
}
