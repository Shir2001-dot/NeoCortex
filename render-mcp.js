#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";

const RENDER_API_KEY = process.env.RENDER_API_KEY;
const BASE_URL = "https://api.render.com/v1";

async function renderRequest(path, method = "GET", body = null) {
    const res = await fetch(`${BASE_URL}${path}`, {
        method,
        headers: {
            "Authorization": `Bearer ${RENDER_API_KEY}`,
            "Content-Type": "application/json",
        },
        body: body ? JSON.stringify(body) : null,
    });
    return res.json();
}

const server = new Server(
    { name: "render-mcp", version: "1.0.0" },
    { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: [
        {
            name: "list_services",
            description: "List all Render services",
            inputSchema: { type: "object", properties: {} },
        },
        {
            name: "get_logs",
            description: "Get logs for a Render service",
            inputSchema: {
                type: "object",
                properties: {
                    serviceId: { type: "string", description: "Service ID" },
                },
                required: ["serviceId"],
            },
        },
        {
            name: "deploy_service",
            description: "Trigger a new deploy for a Render service",
            inputSchema: {
                type: "object",
                properties: {
                    serviceId: { type: "string", description: "Service ID" },
                },
                required: ["serviceId"],
            },
        },
        {
            name: "list_env_vars",
            description: "List environment variables for a service",
            inputSchema: {
                type: "object",
                properties: {
                    serviceId: { type: "string", description: "Service ID" },
                },
                required: ["serviceId"],
            },
        },
        {
            name: "update_env_var",
            description: "Add or update an environment variable",
            inputSchema: {
                type: "object",
                properties: {
                    serviceId: { type: "string", description: "Service ID" },
                    key: { type: "string", description: "Variable name" },
                    value: { type: "string", description: "Variable value" },
                },
                required: ["serviceId", "key", "value"],
            },
        },
    ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
        if (name === "list_services") {
            const data = await renderRequest("/services?limit=20");
            return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
        }

        if (name === "get_logs") {
            const data = await renderRequest(`/services/${args.serviceId}/logs`);
            return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
        }

        if (name === "deploy_service") {
            const data = await renderRequest(`/services/${args.serviceId}/deploys`, "POST", {});
            return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
        }

        if (name === "list_env_vars") {
            const data = await renderRequest(`/services/${args.serviceId}/env-vars`);
            return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
        }

        if (name === "update_env_var") {
            const data = await renderRequest(`/services/${args.serviceId}/env-vars`, "PUT", [
                { key: args.key, value: args.value },
            ]);
            return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
        }

        return { content: [{ type: "text", text: `Unknown tool: ${name}` }] };
    } catch (e) {
        return { content: [{ type: "text", text: `Error: ${e.message}` }] };
    }
});

const transport = new StdioServerTransport();
await server.connect(transport);
